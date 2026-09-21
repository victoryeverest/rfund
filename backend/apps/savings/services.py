"""Savings application services (spec §17–§21, §132)."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction, record_audit
from apps.core.errors import (
    Conflict,
    InsufficientFunds,
    InvalidStateTransition,
    NotFound,
    ValidationFailed,
)
from apps.core.middleware import get_request_id
from apps.core.money import money
from apps.core.references import next_reference
from apps.ledger.services import EntrySpec, post_transaction
from apps.notifications.services import emit_event
from apps.savings.models import (
    SavingsContribution,
    SavingsGoal,
    SavingsPayout,
    SavingsPlan,
    SavingsProduct,
    SavingsScheduleItem,
)
from apps.savings.schedules import generate_schedule_items, project_plan

logger = logging.getLogger("rfund.savings")


DEFAULT_PRODUCTS = [
    {
        "code": "AJO_DAILY",
        "name": "Digital Ajo — Daily",
        "description": "Traditional thrift collection, digitized. Contribute every day.",
        "min_contribution": 100,
        "max_contribution": 50000,
        "allowed_frequencies": ["DAILY"],
        "payout_policy": "END_OF_TERM",
        "allow_early_payout": False,
    },
    {
        "code": "AJO_WEEKLY",
        "name": "Digital Ajo — Weekly",
        "description": "Weekly contributions with quarterly, bi-yearly or yearly payout tenure.",
        "min_contribution": 200,
        "max_contribution": 100000,
        "allowed_frequencies": ["WEEKLY"],
        "payout_policy": "END_OF_TERM",
        "allow_early_payout": False,
    },
    {
        "code": "AJO_MONTHLY",
        "name": "Digital Ajo — Monthly",
        "description": "Monthly contributions with a fixed payout date.",
        "min_contribution": 1000,
        "max_contribution": 500000,
        "allowed_frequencies": ["MONTHLY"],
        "payout_policy": "END_OF_TERM",
        "allow_early_payout": False,
    },
    {
        "code": "SAVE_FLEX",
        "name": "Flexible Savings",
        "description": "Save any amount, any time, for any goal.",
        "min_contribution": 100,
        "max_contribution": 1000000,
        "allowed_frequencies": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "BIYEARLY", "YEARLY"],
        "payout_policy": "ON_DEMAND",
        "allow_early_payout": True,
    },
]


def ensure_default_products() -> None:
    for spec in DEFAULT_PRODUCTS:
        SavingsProduct.objects.get_or_create(
            code=spec["code"], defaults={**spec, "status": "ACTIVE", "version": 1}
        )


def get_product(code: str) -> SavingsProduct:
    product = SavingsProduct.objects.filter(code=code).first()
    if product is None or product.status != "ACTIVE":
        raise NotFound("This savings product is not available.")
    return product


def list_products() -> list[SavingsProduct]:
    return list(SavingsProduct.objects.filter(status="ACTIVE"))


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
@transaction.atomic
def create_savings_plan(
    *,
    customer,
    product_code: str,
    amount,
    frequency: str,
    start_date: date,
    end_date: date,
    created_by=None,
    allow_past_start: bool = False,
) -> SavingsPlan:
    """Create a plan + its calendar schedule.

    `allow_past_start` exists for demo seeding / historical imports only;
    the default rejects backdating for ordinary customer requests.
    """
    product = get_product(product_code)
    amount = money(amount)
    if frequency not in product.allowed_frequencies:
        raise ValidationFailed(
            f"{product.name} supports: {', '.join(product.allowed_frequencies)}."
        )
    if amount < product.min_contribution or amount > product.max_contribution:
        raise ValidationFailed(
            f"Contribution must be between ₦{product.min_contribution:,.0f} and "
            f"₦{product.max_contribution:,.0f} for {product.name}."
        )
    if start_date < date.today() and not allow_past_start:
        raise ValidationFailed("Start date cannot be in the past.")
    if end_date <= start_date:
        raise ValidationFailed("End date must be after the start date.")
    tenure = (end_date - start_date).days
    if tenure > 366 * 5:
        raise ValidationFailed("Plans longer than 5 years are not supported.")

    plan = SavingsPlan(
        reference=next_reference("SAV"),
        customer=customer,
        product=product,
        product_config=product.current_config(),
        amount=amount,
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        status=SavingsPlan.Status.ACTIVE,
        payout_policy=product.payout_policy,
    )
    plan.full_clean()
    plan.save()
    generate_schedule_items(plan)
    record_audit(
        action=AuditAction.CREATE,
        resource_type="savings_plan",
        resource_id=str(plan.pk),
        actor=created_by or customer.user,
        after={"reference": plan.reference, "amount": str(amount), "frequency": frequency},
        request_id=get_request_id(),
    )
    emit_event(
        "SAVINGS_CREATED",
        {
            "customer_id": str(customer.pk),
            "plan_reference": plan.reference,
            "amount": str(amount),
            "frequency": frequency,
        },
    )
    return plan


def get_plan(plan_id: str, *, customer=None) -> SavingsPlan:
    try:
        plan = SavingsPlan.objects.select_related("customer", "product").get(pk=plan_id)
    except (SavingsPlan.DoesNotExist, ValueError):
        raise NotFound("Savings plan not found.")
    if customer is not None and plan.customer_id != customer.pk:
        raise NotFound("Savings plan not found.")  # object-level authz (§111)
    return plan


@transaction.atomic
def cancel_savings_plan(plan: SavingsPlan, *, actor=None, reason: str = "") -> SavingsPlan:
    if plan.status not in (SavingsPlan.Status.ACTIVE, SavingsPlan.Status.PAUSED):
        raise InvalidStateTransition("Only active plans can be cancelled.")
    plan.status = SavingsPlan.Status.CANCELLED
    plan.cancelled_at = timezone.now()
    plan.save(update_fields=["status", "cancelled_at", "updated_at"])
    plan.schedule_items.filter(status=SavingsScheduleItem.Status.UPCOMING).update(
        status=SavingsScheduleItem.Status.CANCELLED
    )
    record_audit(
        action=AuditAction.UPDATE,
        resource_type="savings_plan",
        resource_id=str(plan.pk),
        actor=actor,
        before={"status": "ACTIVE"},
        after={"status": "CANCELLED"},
        reason=reason,
        request_id=get_request_id(),
    )
    return plan


# ---------------------------------------------------------------------------
# Contributions — settled money applied to a plan (called by payments service)
# ---------------------------------------------------------------------------
@transaction.atomic
def apply_contribution_to_plan(payment, ledger_txn) -> SavingsContribution:
    """Apply a SUCCESS payment to its target plan. Idempotent by design."""
    existing = SavingsContribution.objects.filter(payment=payment).first()
    if existing is not None:
        return existing
    target = payment.target or {}
    plan_id = target.get("plan_id")
    if not plan_id:
        raise ValidationFailed("Payment target is missing the savings plan.")
    plan = SavingsPlan.objects.select_for_update().get(pk=plan_id)
    if plan.customer_id != payment.customer_id:
        raise Conflict("Payment customer does not match the plan owner.")
    if plan.status not in (SavingsPlan.Status.ACTIVE, SavingsPlan.Status.PAUSED):
        raise Conflict("This savings plan is no longer active.")

    contribution = SavingsContribution.objects.create(
        plan=plan,
        payment=payment,
        ledger_transaction=ledger_txn,
        amount=payment.amount,
    )
    plan.total_contributed = plan.total_contributed + payment.amount
    plan.save(update_fields=["total_contributed", "updated_at"])

    # Mark schedule items paid, earliest first, tracking partial payments
    # (§21: partial payments). A payment can only satisfy as many items as
    # its amount covers — never mark beyond what was actually paid.
    remaining = payment.amount
    items = plan.schedule_items.filter(
        status__in=[SavingsScheduleItem.Status.UPCOMING, SavingsScheduleItem.Status.DUE, SavingsScheduleItem.Status.MISSED]
    ).order_by("sequence").select_for_update()
    for item in items:
        if remaining <= 0:
            break
        outstanding = item.amount - item.amount_paid
        if outstanding <= 0:
            continue
        take = min(remaining, outstanding)
        item.amount_paid = money(item.amount_paid + take)
        remaining = money(remaining - take)
        if item.amount_paid >= item.amount:
            item.status = SavingsScheduleItem.Status.PAID
            item.paid_at = timezone.now()
            item.payment_reference = payment.reference
            item.save(update_fields=["amount_paid", "status", "paid_at", "payment_reference"])
        else:
            item.save(update_fields=["amount_paid"])

    if _plan_complete(plan):
        plan.status = SavingsPlan.Status.COMPLETED
        plan.completed_at = timezone.now()
        plan.save(update_fields=["status", "completed_at", "updated_at"])

    emit_event(
        "SAVINGS_PAYMENT_RECEIVED",
        {
            "customer_id": str(plan.customer_id),
            "plan_reference": plan.reference,
            "amount": str(payment.amount),
            "payment_reference": payment.reference,
        },
    )
    return contribution


def _plan_complete(plan: SavingsPlan) -> bool:
    total_items = plan.schedule_items.count()
    paid = plan.schedule_items.filter(status=SavingsScheduleItem.Status.PAID).count()
    return total_items > 0 and paid == total_items


@transaction.atomic
def apply_goal_funding(payment, ledger_txn) -> None:
    """Apply a SUCCESS payment to a savings goal. Idempotent."""
    target = payment.target or {}
    goal_id = target.get("goal_id")
    if not goal_id:
        raise ValidationFailed("Payment target is missing the savings goal.")
    goal = SavingsGoal.objects.select_for_update().get(pk=goal_id)
    if goal.customer_id != payment.customer_id:
        raise Conflict("Payment customer does not match the goal owner.")
    if goal.status != SavingsGoal.Status.ACTIVE:
        raise Conflict("This goal is no longer active.")
    goal.current_amount = goal.current_amount + payment.amount
    if goal.current_amount >= goal.target_amount:
        goal.status = SavingsGoal.Status.COMPLETED
        goal.completed_at = timezone.now()
    goal.save()
    emit_event(
        "PAYOUT_COMPLETED" if goal.status == SavingsGoal.Status.COMPLETED else "SAVINGS_PAYMENT_RECEIVED",
        {
            "customer_id": str(goal.customer_id),
            "goal_id": str(goal.pk),
            "amount": str(payment.amount),
        },
    )


# ---------------------------------------------------------------------------
# Payouts (money movement safety — §156)
# ---------------------------------------------------------------------------
@transaction.atomic
def request_savings_payout(plan: SavingsPlan, *, requested_by=None) -> SavingsPayout:
    # Re-read current state: callers may hold a stale object.
    plan = SavingsPlan.objects.select_for_update().get(pk=plan.pk)
    if not plan.product_config.get("allow_early_payout", False):
        if plan.status != SavingsPlan.Status.COMPLETED:
            raise InvalidStateTransition(
                "This plan pays out at the end of its term. It is not complete yet."
            )
    if plan.payouts.filter(status__in=["REQUESTED", "VALIDATED", "APPROVED", "PAID"]).exists():
        raise Conflict("A payout for this plan is already in progress.")
    amount = plan.total_contributed
    if amount <= 0:
        raise InvalidStateTransition("Nothing has been contributed to this plan yet.")
    payout = SavingsPayout.objects.create(
        reference=next_reference("PYT"),
        plan=plan,
        amount=amount,
        status=SavingsPayout.Status.REQUESTED,
        requested_by=requested_by or plan.customer.user,
    )
    emit_event(
        "PAYOUT_COMPLETED",
        {"customer_id": str(plan.customer_id), "payout_reference": payout.reference},
    )
    return payout


@transaction.atomic
def process_savings_payout(payout: SavingsPayout, *, approved_by=None) -> SavingsPayout:
    """Finance-approved payout: posts the ledger movement."""
    if payout.status not in (SavingsPayout.Status.REQUESTED, SavingsPayout.Status.APPROVED):
        raise InvalidStateTransition("This payout cannot be processed.")
    plan = SavingsPlan.objects.select_for_update().get(pk=payout.plan_id)
    if plan.total_contributed < payout.amount:
        raise InsufficientFunds("Plan balance is less than the payout amount.")
    txn = post_transaction(
        txn_type="SAVINGS_PAYOUT",
        description=f"Payout {payout.reference} for plan {plan.reference}",
        currency="NGN",
        entries=[
            EntrySpec(account="SAVINGS_POOL", direction="DEBIT", amount=payout.amount,
                      metadata={"payout": payout.reference}),
            EntrySpec(account="SETTLEMENT", direction="CREDIT", amount=payout.amount,
                      metadata={"payout": payout.reference}),
        ],
        created_by=approved_by,
        external_reference=payout.reference,
        idempotency_key=f"payout:{payout.reference}",
    )
    plan.total_contributed = plan.total_contributed - payout.amount
    plan.save(update_fields=["total_contributed", "updated_at"])
    payout.ledger_transaction = txn
    payout.status = SavingsPayout.Status.PAID
    payout.approved_by = approved_by
    payout.processed_at = timezone.now()
    payout.save()
    record_audit(
        action=AuditAction.SETTLE,
        resource_type="savings_payout",
        resource_id=str(payout.pk),
        actor=approved_by,
        after={"reference": payout.reference, "amount": str(payout.amount)},
        request_id=get_request_id(),
    )
    return payout


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------
@transaction.atomic
def create_goal(
    *,
    customer,
    name: str,
    target_amount,
    target_date=None,
    contribution_frequency: str = "MONTHLY",
    contribution_amount=0,
) -> SavingsGoal:
    target_amount = money(target_amount)
    if target_amount <= 0:
        raise ValidationFailed("Target amount must be greater than zero.")
    if not name.strip():
        raise ValidationFailed("Give your goal a name.")
    if target_date and target_date <= date.today():
        raise ValidationFailed("Target date must be in the future.")
    goal = SavingsGoal(
        customer=customer,
        name=name.strip()[:120],
        target_amount=target_amount,
        target_date=target_date,
        contribution_frequency=contribution_frequency,
        contribution_amount=money(contribution_amount or 0),
    )
    goal.full_clean()
    goal.save()
    return goal


@transaction.atomic
def update_goal(goal: SavingsGoal, *, actor=None, **fields) -> SavingsGoal:
    allowed = {"name", "description", "target_amount", "target_date",
               "contribution_frequency", "contribution_amount"}
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(goal, key, value)
    if goal.target_amount <= 0:
        raise ValidationFailed("Target amount must be greater than zero.")
    goal.full_clean()
    goal.save()
    record_audit(
        action=AuditAction.UPDATE,
        resource_type="savings_goal",
        resource_id=str(goal.pk),
        actor=actor,
        after={"name": goal.name, "target": str(goal.target_amount)},
        request_id=get_request_id(),
    )
    return goal


@transaction.atomic
def delete_goal(goal: SavingsGoal, *, actor=None) -> None:
    """Only goals with no contributions can be removed; others are cancelled."""
    if goal.current_amount > 0:
        goal.status = SavingsGoal.Status.CANCELLED
        goal.save(update_fields=["status", "updated_at"])
        record_audit(
            action=AuditAction.UPDATE,
            resource_type="savings_goal",
            resource_id=str(goal.pk),
            actor=actor,
            before={"status": "ACTIVE"},
            after={"status": "CANCELLED"},
            request_id=get_request_id(),
        )
    else:
        goal.delete()
        record_audit(
            action=AuditAction.DELETE,
            resource_type="savings_goal",
            resource_id=str(goal.pk),
            actor=actor,
            request_id=get_request_id(),
        )


# ---------------------------------------------------------------------------
# Scheduled jobs (Celery beat — idempotent, §154)
# ---------------------------------------------------------------------------
def refresh_schedule_statuses(as_of: date | None = None) -> dict:
    """Mark DUE/MISSED items based on today's date. Idempotent."""
    from datetime import timedelta

    as_of = as_of or timezone.now().date()
    due = SavingsScheduleItem.objects.filter(
        status=SavingsScheduleItem.Status.UPCOMING, due_date__lte=as_of
    ).update(status=SavingsScheduleItem.Status.DUE)
    active_cutoff = as_of - timedelta(days=1)
    missed = SavingsScheduleItem.objects.filter(
        status=SavingsScheduleItem.Status.DUE, due_date__lt=active_cutoff
    ).update(status=SavingsScheduleItem.Status.MISSED)
    # Plans with all items paid or past get completed
    completed = 0
    for plan in SavingsPlan.objects.filter(status=SavingsPlan.Status.ACTIVE).prefetch_related("schedule_items"):
        if _plan_complete(plan):
            plan.status = SavingsPlan.Status.COMPLETED
            plan.completed_at = timezone.now()
            plan.save(update_fields=["status", "completed_at", "updated_at"])
            completed += 1
    return {"marked_due": due, "marked_missed": missed, "plans_completed": completed}
