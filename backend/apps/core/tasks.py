"""Celery tasks (spec §153, §154). All idempotent; truth lives in PostgreSQL."""

from __future__ import annotations

import logging

from config.celery_app import app

logger = logging.getLogger("rfund.tasks")


@app.task(name="rfund.dispatch_outbox")
def dispatch_outbox_task() -> int:
    """Deliver pending notification events (§107 outbox)."""
    from apps.notifications.services import dispatch_outbox

    return dispatch_outbox()


@app.task(name="rfund.refresh_savings_schedules")
def refresh_savings_schedules_task() -> dict:
    """Mark due/missed contributions; complete finished plans."""
    from apps.savings.services import refresh_schedule_statuses

    return refresh_schedule_statuses()


@app.task(name="rfund.apply_late_penalties")
def apply_late_penalties_task() -> dict:
    """Assess penalties on late loan installments per product policy."""
    from apps.loans.services import apply_late_penalties

    return apply_late_penalties()


@app.task(name="rfund.run_reconciliation")
def run_reconciliation_task(provider: str = "local") -> dict:
    from apps.settlements.services import run_reconciliation

    run = run_reconciliation(provider=provider)
    return {"run_id": str(run.pk), "matched": run.matched_count, "exceptions": run.exception_count}


@app.task(name="rfund.snapshot_balances")
def snapshot_balances_task() -> int:
    from apps.ledger.services import snapshot_all_balances

    return snapshot_all_balances()


@app.task(name="rfund.retry_webhooks")
def retry_webhooks_task() -> int:
    from apps.payments.services import retry_failed_webhooks

    return retry_failed_webhooks()


@app.task(name="rfund.savings_reminders")
def savings_reminders_task() -> int:
    """Send due-today reminders via the outbox (§154)."""
    from apps.notifications.services import emit_event
    from apps.savings.models import SavingsScheduleItem

    sent = 0
    for item in SavingsScheduleItem.objects.filter(
        status=SavingsScheduleItem.Status.DUE
    ).select_related("plan__customer"):
        emit_event(
            "SAVINGS_PAYMENT_DUE",
            {
                "customer_id": str(item.plan.customer_id),
                "plan_reference": item.plan.reference,
                "amount": str(item.amount),
            },
        )
        sent += 1
    return sent


@app.task(name="rfund.loan_reminders")
def loan_reminders_task() -> int:
    from apps.loans.models import RepaymentScheduleItem
    from apps.notifications.services import emit_event

    sent = 0
    for item in RepaymentScheduleItem.objects.filter(
        status=RepaymentScheduleItem.Status.DUE
    ).select_related("loan__customer"):
        emit_event(
            "REPAYMENT_DUE",
            {
                "customer_id": str(item.loan.customer_id),
                "loan_reference": item.loan.reference,
                "amount": str(item.total_due - item.amount_paid),
            },
        )
        sent += 1
    return sent
