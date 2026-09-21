"""Loan application services (spec §37, §133)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction, record_audit
from apps.core.errors import (
    Conflict,
    InvalidStateTransition,
    NotFound,
    ValidationFailed,
)
from apps.core.middleware import get_request_id
from apps.core.money import D, money
from apps.core.references import next_reference
from apps.ledger.services import EntrySpec, post_transaction
from apps.loans.calculations import (
    allocate_repayment,
    compute_schedule,
    compute_total_repayable,
)
from apps.loans.models import (
    Loan,
    LoanApplication,
    LoanOffer,
    LoanProduct,
    Penalty,
    Repayment,
    RepaymentScheduleItem,
)
from apps.notifications.services import emit_event

logger = logging.getLogger("rfund.loans")


DEFAULT_PRODUCTS = [
    {
        "code": "TRADER",
        "name": "Trader Loan",
        "description": "Working capital for market traders — inventory, stock and shop needs.",
        "min_amount": 10000,
        "max_amount": 300000,
        "term_values": [3, 6, 9, 12],
        "repayment_frequency": "MONTHLY",
        "interest_method": "FLAT",
        "interest_rate": Decimal("24.0000"),
        "fees": {},
        "penalty_policy": {"late": {"type": "fixed", "value": 500, "grace_days": 3}},
        "allocation_order": ["PENALTY", "FEES", "INTEREST", "PRINCIPAL"],
    },
    {
        "code": "ARTISAN",
        "name": "Artisan Loan",
        "description": "Financing for tools, equipment and raw materials.",
        "min_amount": 5000,
        "max_amount": 150000,
        "term_values": [3, 6, 12],
        "repayment_frequency": "MONTHLY",
        "interest_method": "FLAT",
        "interest_rate": Decimal("26.0000"),
        "fees": {},
        "penalty_policy": {"late": {"type": "fixed", "value": 400, "grace_days": 3}},
        "allocation_order": ["PENALTY", "FEES", "INTEREST", "PRINCIPAL"],
    },
    {
        "code": "FARMERCASH",
        "name": "FarmerCash",
        "description": "Seasonal financing for seeds, fertilizer, labour, transport and storage.",
        "min_amount": 20000,
        "max_amount": 500000,
        "term_values": [6, 9, 12],
        "repayment_frequency": "MONTHLY",
        "interest_method": "FLAT",
        "interest_rate": Decimal("20.0000"),
        "fees": {},
        "penalty_policy": {"late": {"type": "fixed", "value": 600, "grace_days": 7}},
        "allocation_order": ["PENALTY", "FEES", "INTEREST", "PRINCIPAL"],
    },
]


def ensure_default_products() -> None:
    for spec in DEFAULT_PRODUCTS:
        LoanProduct.objects.get_or_create(
            code=spec["code"], defaults={**spec, "status": "ACTIVE", "version": 1}
        )


def list_products() -> list[LoanProduct]:
    return list(LoanProduct.objects.filter(status="ACTIVE"))


def get_product(code: str) -> LoanProduct:
    product = LoanProduct.objects.filter(code=code).first()
    if product is None or product.status != "ACTIVE":
        raise NotFound("This loan product is not available.")
    return product


# ---------------------------------------------------------------------------
# Application flow (§37)
# ---------------------------------------------------------------------------
APPLICATION_TRANSITIONS: dict[str, set[str]] = {
    LoanApplication.State.DRAFT: {"SUBMITTED", "CANCELLED"},
    LoanApplication.State.SUBMITTED: {"UNDER_REVIEW", "APPROVED", "REJECTED", "CANCELLED"},
    LoanApplication.State.UNDER_REVIEW: {
        "VERIFICATION_REQUIRED", "APPROVED", "REJECTED", "CANCELLED",
    },
    LoanApplication.State.VERIFICATION_REQUIRED: {"UNDER_REVIEW", "REJECTED", "CANCELLED"},
    LoanApplication.State.APPROVED: {"OFFERED", "CANCELLED"},
    LoanApplication.State.OFFERED: {"ACCEPTED", "CANCELLED"},  # expiry handled by service
    LoanApplication.State.ACCEPTED: {},  # → loan creation
    LoanApplication.State.REJECTED: {},
    LoanApplication.State.CANCELLED: {},
}


def check_eligibility(customer, product: LoanProduct, amount, term_months: int) -> dict:
    """Deterministic eligibility signals (used in UI + assessment)."""
    from apps.identity.services import get_or_create_profile

    reasons = []
    amount = money(amount)
    if amount < product.min_amount:
        reasons.append(f"Minimum for {product.name} is ₦{product.min_amount:,.0f}.")
    if amount > product.max_amount:
        reasons.append(f"Maximum for {product.name} is ₦{product.max_amount:,.0f}.")
    if term_months not in (product.term_values or []):
        reasons.append(f"Supported terms: {', '.join(str(t) for t in product.term_values)} months.")
    kyc = get_or_create_profile(customer)
    if kyc.status != "VERIFIED":
        reasons.append("Identity verification (KYC) must be completed first.")
    active_loans = Loan.objects.filter(
        customer=customer, status__in=[Loan.Status.ACTIVE, Loan.Status.DELINQUENT]
    ).count()
    if active_loans > 0:
        reasons.append("You already have an active loan.")
    return {"eligible": not reasons, "reasons": reasons}


@transaction.atomic
def create_loan_application(
    *,
    customer,
    product_code: str,
    amount,
    term_months: int,
    purpose: str = "",
    business_info: dict | None = None,
    created_by=None,
) -> LoanApplication:
    product = get_product(product_code)
    amount = money(amount)
    eligibility = check_eligibility(customer, product, amount, term_months)
    if not eligibility["eligible"]:
        raise ValidationFailed(" ".join(eligibility["reasons"]))
    application = LoanApplication(
        reference=next_reference("LAP"),
        customer=customer,
        product=product,
        product_config=product.current_config(),
        amount_requested=amount,
        term_months=term_months,
        purpose=purpose[:2000],
        business_info=business_info or {},
        state=LoanApplication.State.SUBMITTED,
        submitted_at=timezone.now(),
    )
    application.full_clean()
    application.save()
    # Automatic risk assessment on submission (deterministic rules engine §45)
    from apps.risk.services import run_assessment

    run_assessment(application)
    record_audit(
        action=AuditAction.CREATE,
        resource_type="loan_application",
        resource_id=str(application.pk),
        actor=created_by or customer.user,
        after={"reference": application.reference, "amount": str(amount)},
        request_id=get_request_id(),
    )
    emit_event("LOAN_SUBMITTED", {
        "customer_id": str(customer.pk),
        "application_reference": application.reference,
        "amount": str(amount),
    })
    return application


def get_application(application_id: str, *, customer=None) -> LoanApplication:
    try:
        app = LoanApplication.objects.select_related("customer", "product").get(pk=application_id)
    except (LoanApplication.DoesNotExist, ValueError):
        raise NotFound("Loan application not found.")
    if customer is not None and app.customer_id != customer.pk:
        raise NotFound("Loan application not found.")  # object-level authz
    return app


def _transition(application: LoanApplication, new_state: str, *, actor=None, reason=""):
    if new_state not in APPLICATION_TRANSITIONS.get(application.state, set()):
        raise InvalidStateTransition(
            f"Cannot move from {application.state} to {new_state}."
        )
    before = application.state
    application.state = new_state
    if new_state == LoanApplication.State.SUBMITTED:
        application.submitted_at = timezone.now()
    if new_state == LoanApplication.State.REJECTED:
        application.decision_at = timezone.now()
        application.rejection_reason = reason
    if new_state == LoanApplication.State.CANCELLED:
        application.cancelled_at = timezone.now()
    application.save()
    record_audit(
        action=AuditAction.REVIEW,
        resource_type="loan_application",
        resource_id=str(application.pk),
        actor=actor,
        before={"state": before},
        after={"state": new_state},
        reason=reason,
        request_id=get_request_id(),
    )
    return application


@transaction.atomic
def review_application(application: LoanApplication, *, reviewer, notes: str = "") -> LoanApplication:
    require_state(application, LoanApplication.State.SUBMITTED)
    _transition(application, LoanApplication.State.UNDER_REVIEW, actor=reviewer, reason=notes)
    return application


def require_state(application: LoanApplication, expected: str) -> None:
    if application.state != expected:
        raise InvalidStateTransition(
            f"Expected state {expected}, found {application.state}."
        )


@transaction.atomic
def approve_application(
    application: LoanApplication, *, approver, reason: str, amount=None, term_months=None
) -> LoanApplication:
    """LOAN_OFFICER approval — permission checked at resolver; audited here (§165)."""
    if not reason.strip():
        raise ValidationFailed("An approval reason is required for the audit trail.")
    if application.state not in (
        LoanApplication.State.SUBMITTED,
        LoanApplication.State.UNDER_REVIEW,
        LoanApplication.State.VERIFICATION_REQUIRED,
    ):
        raise InvalidStateTransition("Application is not awaiting a decision.")
    # A REJECT assessment is advisory (spec §45: explainable, not autocratic).
    # The officer may override with a mandatory audited reason; the assessment
    # stays attached to the application for the record.

    _transition(application, LoanApplication.State.APPROVED, actor=approver, reason=reason)

    amount = money(amount or application.amount_requested)
    term = term_months or application.term_months
    product = application.product
    if not (product.min_amount <= amount <= product.max_amount):
        raise ValidationFailed("Approved amount is outside the product range.")

    first_payment = date.today() + relativedelta_months(product.repayment_frequency)
    schedule = compute_schedule(
        principal=amount,
        annual_rate_percent=product.interest_rate,
        term_months=term,
        interest_method=product.interest_method,
        first_payment_date=first_payment,
        frequency=product.repayment_frequency,
    )
    total = compute_total_repayable(schedule)
    LoanOffer.objects.update_or_create(
        application=application,
        defaults={
            "amount": amount,
            "interest_rate": product.interest_rate,
            "term_months": term,
            "total_repayable": total,
            "first_payment_date": first_payment,
            "expires_on": date.today() + timedelta(days=14),
            "status": LoanOffer.Status.PENDING,
        },
    )
    _transition(application, LoanApplication.State.OFFERED, actor=approver)
    emit_event("LOAN_APPROVED", {
        "customer_id": str(application.customer_id),
        "application_reference": application.reference,
    })
    return application


def relativedelta_months(frequency: str):
    from dateutil.relativedelta import relativedelta

    return {
        "MONTHLY": relativedelta(months=1),
        "WEEKLY": relativedelta(weeks=1),
        "QUARTERLY": relativedelta(months=3),
        "BIYEARLY": relativedelta(months=6),
        "YEARLY": relativedelta(years=1),
        "DAILY": relativedelta(days=1),
    }[frequency]


@transaction.atomic
def reject_application(application: LoanApplication, *, reviewer, reason: str) -> LoanApplication:
    if not reason.strip():
        raise ValidationFailed("A rejection reason is required.")
    if application.state not in (
        LoanApplication.State.SUBMITTED,
        LoanApplication.State.UNDER_REVIEW,
        LoanApplication.State.VERIFICATION_REQUIRED,
    ):
        raise InvalidStateTransition("Application is not awaiting a decision.")
    _transition(application, LoanApplication.State.REJECTED, actor=reviewer, reason=reason)
    emit_event("LOAN_REJECTED", {
        "customer_id": str(application.customer_id),
        "application_reference": application.reference,
    })
    return application


@transaction.atomic
def accept_offer(application: LoanApplication, *, customer) -> LoanApplication:
    offer = application.offer
    if offer is None:
        raise NotFound("No offer exists for this application.")
    if application.customer_id != customer.pk:
        raise NotFound("Loan application not found.")
    if offer.status != LoanOffer.Status.PENDING:
        raise InvalidStateTransition("This offer has already been handled.")
    if date.today() > offer.expires_on:
        offer.status = LoanOffer.Status.EXPIRED
        offer.save(update_fields=["status"])
        raise InvalidStateTransition("This offer has expired.")
    offer.status = LoanOffer.Status.ACCEPTED
    offer.accepted_at = timezone.now()
    offer.save()
    _transition(application, LoanApplication.State.ACCEPTED, actor=customer.user)
    return application


# ---------------------------------------------------------------------------
# Disbursement + repayment
# ---------------------------------------------------------------------------
@transaction.atomic
def disburse_loan(application: LoanApplication, *, disbursed_by) -> Loan:
    """Disbursement posts the ledger movement (§16: DR Loan Receivable / CR Settlement)."""
    require_state(application, LoanApplication.State.ACCEPTED)
    offer = application.offer
    if offer is None or offer.status != LoanOffer.Status.ACCEPTED:
        raise InvalidStateTransition("The offer must be accepted before disbursement.")

    if Loan.objects.filter(application=application).exists():
        raise Conflict("This application has already been disbursed.")

    product = application.product
    schedule_lines = compute_schedule(
        principal=offer.amount,
        annual_rate_percent=offer.interest_rate,
        term_months=offer.term_months,
        interest_method=product.interest_method,
        first_payment_date=offer.first_payment_date,
        frequency=product.repayment_frequency,
    )

    txn = post_transaction(
        txn_type="LOAN_DISBURSEMENT",
        description=f"Disbursement for loan application {application.reference}",
        currency="NGN",
        entries=[
            EntrySpec(account="LOAN_PRINCIPAL", direction="DEBIT", amount=offer.amount,
                      metadata={"application": application.reference}),
            EntrySpec(account="SETTLEMENT", direction="CREDIT", amount=offer.amount,
                      metadata={"application": application.reference}),
        ],
        created_by=disbursed_by,
        external_reference=application.reference,
        idempotency_key=f"disbursement:{application.reference}",
    )

    loan = Loan.objects.create(
        reference=next_reference("LON"),
        application=application,
        customer=application.customer,
        product=product,
        product_config=application.product_config,
        principal=offer.amount,
        interest_rate=offer.interest_rate,
        interest_method=product.interest_method,
        term_months=offer.term_months,
        total_interest=money(sum(D(l["interest_due"]) for l in schedule_lines)),
        outstanding_principal=offer.amount,
        outstanding_interest=money(sum(D(l["interest_due"]) for l in schedule_lines)),
        outstanding_fees=0,
        status=Loan.Status.ACTIVE,
        disbursed_at=timezone.now(),
        disbursed_by=disbursed_by,
        ledger_transaction=txn,
    )
    RepaymentScheduleItem.objects.bulk_create(
        [
            RepaymentScheduleItem(
                loan=loan,
                sequence=line["sequence"],
                due_date=line["due_date"],
                principal_due=line["principal_due"],
                interest_due=line["interest_due"],
                fees_due=line["fees_due"],
                penalty_due=line["penalty_due"],
            )
            for line in schedule_lines
        ]
    )
    record_audit(
        action=AuditAction.DISBURSE,
        resource_type="loan",
        resource_id=str(loan.pk),
        actor=disbursed_by,
        after={"reference": loan.reference, "principal": str(offer.amount)},
        request_id=get_request_id(),
    )
    emit_event("LOAN_DISBURSED", {
        "customer_id": str(loan.customer_id),
        "loan_reference": loan.reference,
        "amount": str(offer.amount),
    })
    return loan


@transaction.atomic
def apply_repayment_to_loan(payment, ledger_txn) -> Repayment:
    """Apply a successful payment to a loan with deterministic allocation (§41)."""
    existing = Repayment.objects.filter(payment=payment).first()
    if existing is not None:
        return existing
    target = payment.target or {}
    loan_id = target.get("loan_id")
    if not loan_id:
        raise ValidationFailed("Payment target is missing the loan.")
    loan = Loan.objects.select_for_update().get(pk=loan_id)
    if loan.customer_id != payment.customer_id:
        raise Conflict("Payment customer does not match the loan owner.")
    if loan.status not in (Loan.Status.ACTIVE, Loan.Status.DELINQUENT):
        raise Conflict("This loan is not open for repayment.")

    # Outstanding buckets across the whole loan (deterministic)
    penalties_due = money(
        sum(p.amount for p in loan.penalties.filter(status=Penalty.Status.OUTSTANDING))
    )
    fees_due = loan.outstanding_fees
    interest_due = loan.outstanding_interest
    principal_due = loan.outstanding_principal
    order = loan.product_config.get("allocation_order") or [
        "PENALTY", "FEES", "INTEREST", "PRINCIPAL"
    ]
    allocation = allocate_repayment(
        amount=payment.amount,
        penalties_due=penalties_due,
        fees_due=fees_due,
        interest_due=interest_due,
        principal_due=principal_due,
        order=order,
    )

    loan.outstanding_principal = money(
        loan.outstanding_principal - allocation["PRINCIPAL"]
    )
    loan.outstanding_interest = money(
        loan.outstanding_interest - allocation["INTEREST"]
    )
    loan.outstanding_fees = money(loan.outstanding_fees - allocation["FEES"])
    if allocation["PENALTY"] > 0:
        remaining_penalty = allocation["PENALTY"]
        for penalty in loan.penalties.filter(status=Penalty.Status.OUTSTANDING).order_by("created_at"):
            take = min(remaining_penalty, penalty.amount)
            penalty.amount = money(penalty.amount - take)
            penalty.status = Penalty.Status.PAID if penalty.amount == 0 else Penalty.Status.OUTSTANDING
            penalty.save(update_fields=["amount", "status"])
            remaining_penalty = money(remaining_penalty - take)
            if remaining_penalty <= 0:
                break

    # Apply to schedule items in order for display + status accuracy
    remaining = payment.amount
    for item in loan.repayment_schedule.filter(
        status__in=[
            RepaymentScheduleItem.Status.UPCOMING,
            RepaymentScheduleItem.Status.DUE,
            RepaymentScheduleItem.Status.LATE,
            RepaymentScheduleItem.Status.PARTIALLY_PAID,
        ]
    ).order_by("sequence"):
        if remaining <= 0:
            break
        take = min(remaining, item.total_due - item.amount_paid)
        item.amount_paid = money(item.amount_paid + take)
        item.status = (
            RepaymentScheduleItem.Status.PAID
            if item.amount_paid >= item.total_due
            else RepaymentScheduleItem.Status.PARTIALLY_PAID
        )
        item.save(update_fields=["amount_paid", "status"])
        remaining = money(remaining - take)

    if loan.outstanding_principal == 0 and loan.outstanding_interest == 0 and loan.outstanding_fees == 0:
        loan.status = Loan.Status.COMPLETED
        loan.completed_at = timezone.now()

    loan.save()

    repayment = Repayment.objects.create(
        loan=loan,
        payment=payment,
        amount=payment.amount,
        allocation={
            "penalty": str(allocation["PENALTY"]),
            "fees": str(allocation["FEES"]),
            "interest": str(allocation["INTEREST"]),
            "principal": str(allocation["PRINCIPAL"]),
            "unapplied": str(allocation["UNAPPLIED"]),
        },
        ledger_transaction=ledger_txn,
    )
    emit_event("REPAYMENT_RECEIVED", {
        "customer_id": str(loan.customer_id),
        "loan_reference": loan.reference,
        "amount": str(payment.amount),
    })
    return repayment


# ---------------------------------------------------------------------------
# Penalties + delinquency (scheduled job)
# ---------------------------------------------------------------------------
def apply_late_penalties(as_of: date | None = None) -> dict:
    """Assess penalties on late installments per product policy. Idempotent."""
    as_of = as_of or timezone.now().date()
    created = 0
    loans = Loan.objects.filter(status__in=[Loan.Status.ACTIVE, Loan.Status.DELINQUENT])
    for loan in loans.prefetch_related("repayment_schedule", "penalties"):
        policy = (loan.product_config or {}).get("penalty_policy") or {}
        late_cfg = policy.get("late") or {}
        grace = int(late_cfg.get("grace_days", 3))
        value = D(late_cfg.get("value", 0))
        if value <= 0:
            continue
        for item in loan.repayment_schedule.filter(
            status__in=[RepaymentScheduleItem.Status.DUE, RepaymentScheduleItem.Status.LATE]
        ):
            overdue_days = (as_of - item.due_date).days
            if overdue_days <= grace:
                continue
            already = loan.penalties.filter(schedule_item=item).exists()
            if already:
                continue
            Penalty.objects.create(
                loan=loan,
                schedule_item=item,
                amount=money(value),
                reason=f"Installment {item.sequence} {overdue_days} days overdue",
            )
            item.status = RepaymentScheduleItem.Status.LATE
            item.save(update_fields=["status"])
            created += 1
        if any(
            (as_of - it.due_date).days > grace
            for it in loan.repayment_schedule.filter(
                status__in=[RepaymentScheduleItem.Status.LATE, RepaymentScheduleItem.Status.DUE]
            )
        ):
            loan.status = Loan.Status.DELINQUENT
            loan.save(update_fields=["status", "updated_at"])
            emit_event("REPAYMENT_LATE", {
                "customer_id": str(loan.customer_id),
                "loan_reference": loan.reference,
            })
    return {"penalties_created": created}
