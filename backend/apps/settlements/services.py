"""Reconciliation services (spec §27, §201).

Compares RFUND's ledger-backed payments with the provider transaction
mirror (PaymentProviderEvent) and raises exceptions for humans to
resolve. Runs are idempotent and re-runnable.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import NotFound, ValidationFailed
from apps.payments.models import Payment, PaymentProviderEvent
from apps.settlements.models import (
    ReconciliationException,
    ReconciliationItem,
    ReconciliationRun,
)

logger = logging.getLogger("rfund.settlements")


@transaction.atomic
def run_reconciliation(
    *,
    provider: str,
    period_start=None,
    period_end=None,
) -> ReconciliationRun:
    period_end = period_end or timezone.now()
    period_start = period_start or period_end - timedelta(hours=24)

    run = ReconciliationRun.objects.create(
        provider=provider,
        period_start=period_start,
        period_end=period_end,
        status=ReconciliationRun.Status.RUNNING,
    )

    internal = Payment.objects.filter(
        provider=provider,
        status__in=[Payment.Status.SUCCESS, Payment.Status.SETTLED],
        created_at__range=(period_start, period_end),
    )
    # Provider mirrors may lack occurred_at (manual/backfilled) — fall back
    # to created_at so nothing silently escapes reconciliation.
    from django.db.models.functions import Coalesce

    provider_events = PaymentProviderEvent.objects.filter(
        provider=provider,
    ).annotate(
        effective_at=Coalesce("occurred_at", "created_at")
    ).filter(effective_at__range=(period_start, period_end))

    internal_by_ref = {p.provider_reference: p for p in internal}
    provider_by_ref = {e.provider_reference: e for e in provider_events}

    matched = exceptions = 0

    # Provider events → internal payments
    for ref, event in provider_by_ref.items():
        payment = internal_by_ref.get(ref)
        if payment is None:
            item = ReconciliationItem.objects.create(
                run=run,
                provider_reference=ref,
                provider_amount=event.amount,
                status=ReconciliationItem.Status.MISSING_INTERNAL,
            )
            _raise_exception(item, "Provider transaction has no matching RFUND payment.")
            exceptions += 1
            continue
        if payment.amount != event.amount:
            item = ReconciliationItem.objects.create(
                run=run,
                internal_reference=payment.reference,
                provider_reference=ref,
                internal_amount=payment.amount,
                provider_amount=event.amount,
                status=ReconciliationItem.Status.AMOUNT_MISMATCH,
            )
            _raise_exception(
                item,
                f"Amount mismatch: internal {payment.amount} vs provider {event.amount}.",
            )
            exceptions += 1
        else:
            ReconciliationItem.objects.create(
                run=run,
                internal_reference=payment.reference,
                provider_reference=ref,
                internal_amount=payment.amount,
                provider_amount=event.amount,
                status=ReconciliationItem.Status.MATCHED,
            )
            event.reconciled = True
            event.save(update_fields=["reconciled"])
            matched += 1

    # Internal payments missing on provider
    for ref, payment in internal_by_ref.items():
        if ref and ref not in provider_by_ref:
            item = ReconciliationItem.objects.create(
                run=run,
                internal_reference=payment.reference,
                provider_reference=ref,
                internal_amount=payment.amount,
                status=ReconciliationItem.Status.MISSING_PROVIDER,
            )
            _raise_exception(item, "RFUND payment has no provider transaction.")
            exceptions += 1

    run.matched_count = matched
    run.exception_count = exceptions
    run.status = ReconciliationRun.Status.COMPLETED
    run.finished_at = timezone.now()
    run.save()
    logger.info(
        "reconciliation_run_completed",
        extra={
            "event": "reconciliation_run_completed",
            "provider": provider,
            "status": "COMPLETED",
            "structured": {"matched": matched, "exceptions": exceptions},
        },
    )
    return run


def _raise_exception(item: ReconciliationItem, reason: str) -> None:
    ReconciliationException.objects.create(item=item, reason=reason)


@transaction.atomic
def resolve_exception(exception_id: str, *, resolver, resolution: str) -> ReconciliationException:
    try:
        exc = ReconciliationException.objects.select_related("item").get(pk=exception_id)
    except (ReconciliationException.DoesNotExist, ValueError):
        raise NotFound("Reconciliation exception not found.")
    if exc.resolved_at is not None:
        raise ValidationFailed("This exception is already resolved.")
    if not resolution.strip():
        raise ValidationFailed("A resolution note is required.")
    exc.resolution = resolution
    exc.resolved_by = resolver
    exc.resolved_at = timezone.now()
    exc.save()
    exc.item.status = ReconciliationItem.Status.MANUAL_REVIEW
    exc.item.save(update_fields=["status"])
    return exc
