"""Notifications with the outbox pattern (spec §47, §48, §107).

emit_event() persists an outbox row in the CURRENT transaction — if the
financial transaction rolls back, so does the notification. A Celery task
(or eager dispatch in dev/test) then renders templates and delivers via
provider adapters. Notification failure can never break money movement.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("rfund.notifications")


EVENT_LABELS = {
    "ACCOUNT_CREATED": "Account created",
    "KYC_SUBMITTED": "Identity submitted",
    "KYC_VERIFIED": "Identity verified",
    "SAVINGS_CREATED": "Savings plan created",
    "SAVINGS_PAYMENT_DUE": "Savings payment due",
    "SAVINGS_PAYMENT_RECEIVED": "Savings payment received",
    "SAVINGS_MISSED": "Savings payment missed",
    "PAYMENT_SUCCESS": "Payment successful",
    "PAYMENT_FAILED": "Payment failed",
    "LOAN_SUBMITTED": "Loan application submitted",
    "LOAN_APPROVED": "Loan approved",
    "LOAN_REJECTED": "Loan rejected",
    "LOAN_DISBURSED": "Loan disbursed",
    "REPAYMENT_DUE": "Loan repayment due",
    "REPAYMENT_RECEIVED": "Loan repayment received",
    "REPAYMENT_LATE": "Loan repayment late",
    "PAYOUT_COMPLETED": "Payout processed",
    "SECURITY_ALERT": "Security alert",
}


def emit_event(event_code: str, payload: dict) -> None:
    """Persist an outbox event inside the caller's transaction (§107)."""
    from apps.notifications.models import OutboxEvent

    OutboxEvent.objects.create(event_code=event_code, payload=payload)


def dispatch_outbox(limit: int = 100) -> int:
    """Deliver pending outbox events. Idempotent; safe to re-run."""
    from apps.notifications.models import NotificationDelivery, OutboxEvent

    pending = OutboxEvent.objects.filter(dispatched=False).order_by("created_at")[:limit]
    delivered = 0
    for event in pending:
        with transaction.atomic():
            # Lock the row: two workers must not both deliver.
            locked = OutboxEvent.objects.select_for_update().get(pk=event.pk)
            if locked.dispatched:
                continue
            recipients = _resolve_recipients(locked)
            for channel, recipient, language in recipients:
                delivery = _render_and_deliver(locked, channel, recipient, language)
                delivered += 1
            locked.dispatched = True
            locked.dispatched_at = timezone.now()
            locked.save(update_fields=["dispatched", "dispatched_at"])
    return delivered


def _resolve_recipients(event) -> list[tuple[str, str, str]]:
    """Determine (channel, recipient, language) for an event."""
    from apps.customers.models import Customer

    payload = event.payload or {}
    customer_id = payload.get("customer_id") or payload.get("user_id")
    if not customer_id:
        return []
    customer = Customer.objects.filter(pk=customer_id).select_related("user").first()
    if customer is None:
        # user events without a customer profile: fall back to user phone
        from apps.accounts.models import User

        user = User.objects.filter(pk=customer_id).first()
        if user is not None:
            return [("SMS", user.phone, "en")]
        return []
    recipients = [("SMS", customer.phone, customer.preferred_language or "en")]
    if customer.email:
        recipients.append(("EMAIL", customer.email, customer.preferred_language or "en"))
    return recipients


def _render_and_deliver(event, channel: str, recipient: str, language: str):
    from apps.notifications.models import NotificationDelivery, NotificationTemplate

    template = NotificationTemplate.objects.filter(
        event_code=event.event_code, channel=channel, language=language, active=True
    ).first() or NotificationTemplate.objects.filter(
        event_code=event.event_code, channel=channel, language="en", active=True
    ).first()

    subject, body = "", ""
    if template:
        subject = template.render_subject(event.payload or {})
        body = template.render_body(event.payload or {})
    else:
        label = EVENT_LABELS.get(event.event_code, event.event_code)
        subject = f"RFUND: {label}"
        body = f"Reference details: {event.payload.get('reference') or event.payload.get('plan_reference') or ''}".strip()

    delivery = NotificationDelivery.objects.create(
        event=event,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        status="PENDING",
    )
    return _send_delivery(delivery)


def _send_delivery(delivery):
    from apps.notifications.models import NotificationDelivery

    try:
        if delivery.channel == "SMS":
            from integrations.messaging.providers import send_sms_message

            send_sms_message(phone=delivery.recipient, message=delivery.body)
        elif delivery.channel == "EMAIL":
            from django.conf import settings
            from django.core.mail import send_mail

            send_mail(
                subject=delivery.subject or "RFUND",
                message=delivery.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[delivery.recipient],
                fail_silently=False,
            )
        delivery.status = "SENT"
        delivery.attempts += 1
        delivery.sent_at = timezone.now()
    except Exception as exc:
        delivery.status = "FAILED" if delivery.attempts >= 3 else "PENDING"
        delivery.attempts += 1
        delivery.error = str(exc)[:250]
    delivery.save()
    return delivery


DEFAULT_TEMPLATES = [
    ("SAVINGS_PAYMENT_RECEIVED", "SMS", "en", "RFUND savings",
     "Payment received: {amount} Naira. Ref: {payment_reference}. Thank you for saving with RFUND."),
    ("PAYMENT_SUCCESS", "SMS", "en", "RFUND payment",
     "Your payment of {amount} Naira was successful. Ref: {reference}."),
    ("PAYMENT_FAILED", "SMS", "en", "RFUND payment",
     "Your payment of {amount} Naira did not go through. Please try again or contact support."),
    ("LOAN_DISBURSED", "SMS", "en", "RFUND loan",
     "Your loan of {amount} Naira has been disbursed. Ref: {loan_reference}."),
    ("REPAYMENT_RECEIVED", "SMS", "en", "RFUND repayment",
     "Repayment of {amount} Naira received. Loan: {loan_reference}."),
    ("LOAN_APPROVED", "SMS", "en", "RFUND loan",
     "Good news! Your loan application {application_reference} is approved."),
    ("KYC_VERIFIED", "SMS", "en", "RFUND identity",
     "Your identity has been verified. You can now access all RFUND services."),
    ("SAVINGS_PAYMENT_DUE", "SMS", "en", "RFUND savings",
     "Reminder: your savings contribution is due today."),
    ("REPAYMENT_DUE", "SMS", "en", "RFUND loan",
     "Reminder: your loan repayment is due today. Ref: {loan_reference}."),
]


def ensure_default_templates() -> None:
    from apps.notifications.models import NotificationTemplate

    for code, channel, language, subject, body in DEFAULT_TEMPLATES:
        NotificationTemplate.objects.get_or_create(
            event_code=code, channel=channel, language=language,
            defaults={"subject": subject, "body": body, "active": True},
        )
