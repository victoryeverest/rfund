"""Payment application services (spec §22–§28, §106, §109).

Flow:
  initialize_payment → provider call → PaymentAttempt → PENDING
  webhook OR verify_payment → server-side verification → settle:
      transaction.atomic:
        payment SUCCESS + ledger posting + domain settlement
          (savings contribution / goal funding / loan repayment)
        + outbox notification event
Idempotency everywhere: same key or same provider event ⇒ exactly one
financial effect (§3.5, §25).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import (
    Conflict,
    NotFound,
    ValidationFailed,
)
from apps.core.middleware import get_request_id
from apps.core.money import money
from apps.core.references import next_reference
from apps.ledger.services import EntrySpec, post_transaction
from apps.notifications.services import emit_event
from apps.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentProviderEvent,
    PaymentWebhookEvent,
)
from integrations.payments.base import get_payment_provider

logger = logging.getLogger("rfund.payments")


def get_payment(payment_id: str) -> Payment:
    try:
        return Payment.objects.select_related("customer__user").get(pk=payment_id)
    except (Payment.DoesNotExist, ValueError):
        raise NotFound("Payment not found.")


def get_payment_by_reference(reference: str) -> Payment:
    payment = Payment.objects.select_related("customer__user").filter(reference=reference).first()
    if payment is None:
        raise NotFound("Payment not found.")
    return payment


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def initialize_payment(
    *,
    customer,
    purpose: str,
    amount: Decimal | int | str,
    currency: str = "NGN",
    target: dict | None = None,
    idempotency_key: str = "",
    initiated_by=None,
    device_id: str = "",
    client_reference: str = "",
    channels: list[str] | None = None,
) -> tuple[Payment, str]:
    """Create Payment + provider attempt. Returns (payment, authorization_url)."""
    amount = money(amount)
    if amount <= 0:
        raise ValidationFailed("Payment amount must be greater than zero.")
    if purpose not in Payment.Purpose.values:
        raise ValidationFailed("Invalid payment purpose.")

    # Idempotent replay
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if (
                existing.amount != amount
                or existing.purpose != purpose
                or existing.customer_id != customer.pk
            ):
                raise Conflict(
                    "This request was already processed with different details."
                )
            url = (
                existing.attempts.order_by("-created_at")
                .values_list("authorization_url", flat=True)
                .first()
                or ""
            )
            return existing, url

    provider = get_payment_provider()
    payment = Payment(
        reference=next_reference("PAY"),
        customer=customer,
        purpose=purpose,
        amount=amount,
        currency=currency,
        status=Payment.Status.INITIALIZED,
        provider=provider.code,
        idempotency_key=idempotency_key,
        target=_jsonable(target or {}),
        initiated_by=initiated_by or customer.user,
        device_id=device_id,
        client_reference=client_reference,
    )
    try:
        result = provider.initialize_payment(
            reference=payment.reference,
            amount=amount,
            currency=currency,
            email=customer.email or f"{customer.phone[-4:]}@rfund.example",
            metadata={"internal_reference": payment.reference, "purpose": purpose},
            channels=channels,
        )
    except Exception:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = "Provider initialization failed"
        payment.save()
        raise

    payment.provider_reference = result.provider_reference
    payment.status = Payment.Status.PENDING
    payment.save()
    PaymentAttempt.objects.create(
        payment=payment,
        provider=provider.code,
        provider_reference=result.provider_reference,
        amount=amount,
        currency=currency,
        status="PENDING",
        authorization_url=result.authorization_url,
        raw_response={"status": "PENDING"},
    )
    logger.info(
        "payment_initialized",
        extra={
            "event": "payment_initialized",
            "reference": payment.reference,
            "operation": "initialize_payment",
        },
    )
    return payment, result.authorization_url


def _jsonable(value):
    """Coerce arbitrary values into JSON-safe primitives (UUID, date, Decimal…)."""
    import json

    return json.loads(json.dumps(value, default=str))


# ---------------------------------------------------------------------------
# Settlement — the ONLY path where money lands
# ---------------------------------------------------------------------------
def settle_payment(
    payment: Payment,
    *,
    provider_reference: str,
    amount: Decimal,
    currency: str,
    method: str = "",
    paid_at=None,
    source: str = "verification",
) -> Payment:
    """Mark SUCCESS + post ledger + settle the domain target. Idempotent."""
    if payment.status in (Payment.Status.SUCCESS, Payment.Status.SETTLED):
        return payment  # already settled — duplicate webhook/verify
    if payment.status in (Payment.Status.CANCELLED, Payment.Status.REVERSED):
        raise Conflict("This payment was cancelled or reversed; it cannot succeed.")

    amount = money(amount)
    if amount != payment.amount:
        raise Conflict(
            f"Provider amount {amount} does not match expected {payment.amount}. "
            "Reconciliation exception required."
        )
    if currency != payment.currency:
        raise Conflict("Provider currency does not match the payment currency.")

    with transaction.atomic():
        # Re-fetch with lock to serialize concurrent webhook + verification.
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status in (Payment.Status.SUCCESS, Payment.Status.SETTLED):
            return locked
        if locked.status in (Payment.Status.CANCELLED, Payment.Status.REVERSED):
            raise Conflict("Payment can no longer succeed.")

        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT" if locked.purpose != "LOAN_REPAYMENT" else "LOAN_REPAYMENT",
            description=f"Payment {locked.reference} ({locked.purpose})",
            currency=currency,
            entries=[
                EntrySpec(
                    account="SETTLEMENT",
                    direction="DEBIT",
                    amount=amount,
                    metadata={"payment": locked.reference},
                ),
                EntrySpec(
                    account="SAVINGS_POOL",
                    direction="CREDIT",
                    amount=amount,
                    metadata={"payment": locked.reference, "customer": str(locked.customer_id)},
                ),
            ]
            if locked.purpose != "LOAN_REPAYMENT"
            else [
                EntrySpec(
                    account="SETTLEMENT",
                    direction="DEBIT",
                    amount=amount,
                    metadata={"payment": locked.reference},
                ),
                EntrySpec(
                    account="LOAN_PRINCIPAL",
                    direction="CREDIT",
                    amount=amount,
                    metadata={"payment": locked.reference},
                ),
            ],
            created_by=None,
            external_reference=provider_reference,
            idempotency_key=f"payment:{locked.reference}",
        )
        locked.ledger_transaction = txn
        locked.status = Payment.Status.SUCCESS
        locked.completed_at = timezone.now()
        locked.method = method or locked.method
        locked.provider_reference = locked.provider_reference or provider_reference
        locked.save()

        _settle_domain_target(locked, txn)

    emit_event(
        "PAYMENT_SUCCESS",
        {
            "payment_id": str(locked.pk),
            "reference": locked.reference,
            "amount": str(amount),
            "customer_id": str(locked.customer_id),
            "purpose": locked.purpose,
        },
    )
    return locked


def _settle_domain_target(payment: Payment, ledger_txn) -> None:
    """Route the settled money to its domain target (inside the txn)."""
    target = payment.target or {}
    purpose = payment.purpose
    if purpose == Payment.Purpose.SAVINGS_CONTRIBUTION:
        from apps.savings.services import apply_contribution_to_plan

        apply_contribution_to_plan(payment, ledger_txn)
    elif purpose == Payment.Purpose.GOAL_FUNDING:
        from apps.savings.services import apply_goal_funding

        apply_goal_funding(payment, ledger_txn)
    elif purpose == Payment.Purpose.LOAN_REPAYMENT:
        from apps.loans.services import apply_repayment_to_loan

        apply_repayment_to_loan(payment, ledger_txn)
    elif purpose == Payment.Purpose.ACCOUNT_FUNDING:
        pass  # money already in SAVINGS_POOL (customer's aggregate savings)
    else:  # pragma: no cover
        raise Conflict(f"Unroutable payment purpose: {purpose}")


# ---------------------------------------------------------------------------
# Server-side verification (authoritative — §23)
# ---------------------------------------------------------------------------
def verify_and_settle(payment: Payment) -> Payment:
    """Poll the provider and settle if successful."""
    if payment.status in (Payment.Status.SUCCESS, Payment.Status.SETTLED):
        return payment
    provider = get_payment_provider()
    if payment.provider and payment.provider != provider.code:
        # Payment belongs to a different provider (e.g. created before a
        # config change) — fetch that provider explicitly.
        provider = get_payment_provider(payment.provider)
    result = provider.verify_payment(provider_reference=payment.provider_reference)
    if result.status == "SUCCESS":
        return settle_payment(
            payment,
            provider_reference=result.provider_reference,
            amount=result.amount,
            currency=result.currency,
            method=result.method,
            paid_at=result.paid_at,
            source="verification",
        )
    if result.status == "FAILED":
        payment.status = Payment.Status.FAILED
        payment.failure_reason = "Provider reported failure"
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        emit_event(
            "PAYMENT_FAILED",
            {"reference": payment.reference, "customer_id": str(payment.customer_id)},
        )
    return payment


# ---------------------------------------------------------------------------
# Webhook ingestion (§25, §109)
# ---------------------------------------------------------------------------
def ingest_webhook(
    *,
    provider_code: str,
    event_id: str,
    event_type: str,
    payload: dict,
    signature_valid: bool,
) -> PaymentWebhookEvent:
    """Persist the raw event first; never lose events (§25)."""
    event, created = PaymentWebhookEvent.objects.get_or_create(
        provider=provider_code,
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "payload": payload,
            "signature_valid": signature_valid,
            "processing_status": "RECEIVED",
        },
    )
    if not created:
        if not event.signature_valid and signature_valid:
            event.signature_valid = True
            event.save(update_fields=["signature_valid"])
        logger.info(
            "webhook_duplicate_event_ignored",
            extra={"event_id": event.event_id, "provider": provider_code},
        )
    return event


def process_webhook_event(event: PaymentWebhookEvent) -> PaymentWebhookEvent:
    """Process a stored webhook event exactly once (idempotent, §25)."""
    if not event.signature_valid:
        event.processing_status = "FAILED"
        event.processing_error = "Invalid signature — event stored, not processed."
        event.save(update_fields=["processing_status", "processing_error"])
        return event
    if event.processing_status == "PROCESSED":
        return event

    event.attempts += 1
    try:
        with transaction.atomic():
            payload = event.payload or {}
            provider_code = event.provider
            event_type = event.event_type or payload.get("event", "")
            data = payload.get("data") or {}

            if event_type == "charge.success":
                provider_reference = str(data.get("reference", ""))
                amount_major = Decimal(str(data.get("amount", 0))) / 100
                payment = (
                    Payment.objects.select_for_update()
                    .filter(provider_reference=provider_reference)
                    .first()
                )
                if payment is None:
                    # Also look up by our own reference carried in metadata
                    internal = (data.get("metadata") or {}).get("internal_reference", "")
                    payment = (
                        Payment.objects.select_for_update()
                        .filter(reference=internal)
                        .first()
                    )
                if payment is None:
                    raise Conflict(
                        f"No payment matches provider reference {provider_reference!r}"
                    )
                settled = settle_payment(
                    payment,
                    provider_reference=provider_reference,
                    amount=amount_major,
                    currency=str(data.get("currency", "NGN")),
                    method=str(data.get("channel", "")).upper()[:16],
                    paid_at=data.get("paid_at"),
                    source="webhook",
                )
                event.payment = settled

                # Mirror the provider transaction for reconciliation
                PaymentProviderEvent.objects.update_or_create(
                    provider=provider_code,
                    provider_reference=provider_reference,
                    defaults={
                        "event_type": event_type,
                        "amount": amount_major,
                        "currency": str(data.get("currency", "NGN")),
                        "status": "SUCCESS",
                        "occurred_at": timezone.now(),
                        "raw": payload,
                        "reconciled": True,
                    },
                )
            else:
                # Non-money events are stored but require no ledger action.
                logger.info(
                    "webhook_non_charge_event_stored",
                    extra={"event_id": event.event_id, "provider": provider_code},
                )
            event.processing_status = "PROCESSED"
            event.processed_at = timezone.now()
            event.processing_error = ""
    except Exception as exc:
        event.processing_status = (
            "DEAD" if event.attempts >= 5 else "FAILED"
        )
        event.processing_error = str(exc)[:500]
        logger.error(
            "webhook_processing_failed",
            extra={"event_id": event.event_id, "provider": provider_code},
        )
    event.save()
    return event


def retry_failed_webhooks() -> int:
    """Celery beat job: retry FAILED webhook events with backoff (§152)."""
    retryable = PaymentWebhookEvent.objects.filter(
        processing_status__in=["RECEIVED", "FAILED"], signature_valid=True
    )
    count = 0
    for event in retryable:
        process_webhook_event(event)
        count += 1
    return count
