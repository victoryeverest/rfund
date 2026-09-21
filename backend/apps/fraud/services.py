"""Fraud detection services (spec §46, §160).

Deterministic detectors raise alerts into an investigation workflow.
No auto-conviction: a person is only "CONFIRMED" after human review.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction, record_audit
from apps.core.middleware import get_request_id
from apps.fraud.models import FraudAlert, FraudCase, FraudRule

logger = logging.getLogger("rfund.fraud")


DEFAULT_RULES = [
    {"code": "PAYMENT_VELOCITY", "detector": "payment_velocity",
     "parameters": {"max_per_hour": 10}, "description": "Abnormal payment attempt frequency."},
    {"code": "DUPLICATE_AMOUNT_BURST", "detector": "duplicate_amount_burst",
     "parameters": {"window_minutes": 10, "max_repeats": 4}, "description": "Repeated identical amounts in a short window."},
    {"code": "FAILED_ATTEMPT_BURST", "detector": "failed_attempt_burst",
     "parameters": {"window_minutes": 30, "max_failures": 5}, "description": "Repeated failed payment attempts."},
    {"code": "AGENT_VELOCITY", "detector": "agent_velocity",
     "parameters": {"max_per_hour": 30}, "description": "Agent transacting abnormally fast."},
    {"code": "AGENT_AMOUNT_ANOMALY", "detector": "agent_amount_anomaly",
     "parameters": {"multiplier": 5}, "description": "Agent single transaction far above personal history."},
]


def ensure_default_rules() -> None:
    for spec in DEFAULT_RULES:
        FraudRule.objects.get_or_create(
            code=spec["code"], defaults={k: v for k, v in spec.items() if k != "code"}
        )


def raise_alert(
    *, rule: FraudRule, resource_type: str, resource_id: str,
    severity: str = "MEDIUM", details: dict | None = None,
) -> FraudAlert | None:
    alert = FraudAlert.objects.create(
        rule=rule, resource_type=resource_type, resource_id=str(resource_id),
        severity=severity, details=details or {},
    )
    logger.warning(
        "fraud_alert_raised",
        extra={"event": "fraud_alert_raised", "reference": alert.pk, "provider": rule.code},
    )
    from apps.notifications.services import emit_event

    emit_event("SECURITY_ALERT", {"alert_id": str(alert.pk), "rule": rule.code})
    return alert


@transaction.atomic
def check_payment_patterns(payment) -> None:
    """Runs after payment initialization. Cheap, deterministic."""
    now = timezone.now()
    customer = payment.customer

    velocity = FraudRule.objects.filter(code="PAYMENT_VELOCITY", active=True).first()
    if velocity:
        limit = int((velocity.parameters or {}).get("max_per_hour", 10))
        recent = customer.payments.filter(created_at__gte=now - timedelta(hours=1)).count()
        if recent > limit:
            raise_alert(
                rule=velocity, resource_type="customer", resource_id=str(customer.pk),
                severity="HIGH", details={"payments_last_hour": recent, "limit": limit},
            )

    dup = FraudRule.objects.filter(code="DUPLICATE_AMOUNT_BURST", active=True).first()
    if dup:
        params = dup.parameters or {}
        window = timedelta(minutes=int(params.get("window_minutes", 10)))
        max_repeats = int(params.get("max_repeats", 4))
        repeats = customer.payments.filter(
            amount=payment.amount, created_at__gte=now - window
        ).count()
        if repeats > max_repeats:
            raise_alert(
                rule=dup, resource_type="customer", resource_id=str(customer.pk),
                details={"repeats": repeats, "amount": str(payment.amount)},
            )

    failed = FraudRule.objects.filter(code="FAILED_ATTEMPT_BURST", active=True).first()
    if failed:
        params = failed.parameters or {}
        window = timedelta(minutes=int(params.get("window_minutes", 30)))
        max_failures = int(params.get("max_failures", 5))
        failures = customer.payments.filter(
            status="FAILED", created_at__gte=now - window
        ).count()
        if failures > max_failures:
            raise_alert(
                rule=failed, resource_type="customer", resource_id=str(customer.pk),
                details={"failures": failures},
            )


@transaction.atomic
def check_agent_transaction(agent_txn) -> None:
    now = timezone.now()
    agent = agent_txn.agent

    velocity = FraudRule.objects.filter(code="AGENT_VELOCITY", active=True).first()
    if velocity:
        limit = int((velocity.parameters or {}).get("max_per_hour", 30))
        recent = agent.transactions.filter(performed_at__gte=now - timedelta(hours=1)).count()
        if recent > limit:
            raise_alert(
                rule=velocity, resource_type="agent", resource_id=str(agent.pk),
                severity="HIGH", details={"txns_last_hour": recent},
            )

    anomaly = FraudRule.objects.filter(code="AGENT_AMOUNT_ANOMALY", active=True).first()
    if anomaly:
        multiplier = Decimal(str((anomaly.parameters or {}).get("multiplier", 5)))
        avg = agent.transactions.exclude(pk=agent_txn.pk).order_by("-performed_at")[:20]
        if avg:
            amounts = [t.amount for t in avg]
            average = sum(amounts) / len(amounts)
            if average > 0 and agent_txn.amount > average * multiplier:
                raise_alert(
                    rule=anomaly, resource_type="agent", resource_id=str(agent.pk),
                    details={"amount": str(agent_txn.amount), "average": str(average)},
                )


@transaction.atomic
def review_alert(alert: FraudAlert, *, reviewer, decision: str, notes: str = "") -> FraudAlert:
    if alert.status not in (FraudAlert.Status.FLAGGED, FraudAlert.Status.UNDER_REVIEW):
        from apps.core.errors import InvalidStateTransition

        raise InvalidStateTransition("This alert is already resolved.")
    if decision not in ("UNDER_REVIEW", "CLEARED", "CONFIRMED"):
        from apps.core.errors import ValidationFailed

        raise ValidationFailed("Invalid review decision.")
    alert.status = decision
    alert.assigned_to = reviewer
    alert.save(update_fields=["status", "assigned_to"])
    if decision in ("CLEARED", "CONFIRMED"):
        FraudCase.objects.update_or_create(
            alert=alert,
            defaults={
                "investigation_notes": notes,
                "outcome": decision,
                "resolved_by": reviewer,
                "resolved_at": timezone.now(),
            },
        )
    record_audit(
        action=AuditAction.REVIEW,
        resource_type="fraud_alert",
        resource_id=str(alert.pk),
        actor=reviewer,
        before={"status": "FLAGGED"},
        after={"status": decision},
        reason=notes,
        request_id=get_request_id(),
    )
    return alert
