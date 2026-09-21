"""Loan calculation + journey tests (spec §39–§41, §200)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.errors import InvalidStateTransition, ValidationFailed
from apps.loans.calculations import (
    allocate_repayment,
    compute_declining_schedule,
    compute_flat_interest,
    compute_schedule,
    compute_total_repayable,
)
from apps.loans.models import Loan, LoanApplication, RepaymentScheduleItem
from apps.loans.services import (
    accept_offer,
    approve_application,
    apply_late_penalties,
    apply_repayment_to_loan,
    check_eligibility,
    create_loan_application,
    disburse_loan,
    ensure_default_products,
    reject_application,
)
from apps.payments.services import initialize_payment, settle_payment
from tests.factories import make_customer, make_loan_product, verify_kyc


@pytest.fixture(autouse=True)
def _products(db):
    from apps.ledger.services import ensure_core_accounts

    ensure_core_accounts()
    ensure_default_products()


class TestFlatInterest:
    def test_flat_formula(self):
        # 100k @ 24% for 6 months: 100000 × 0.24 × 6/12 = 12000
        assert compute_flat_interest(100000, 24, 6) == Decimal("12000.00")

    def test_zero_rate(self):
        assert compute_flat_interest(50000, 0, 12) == Decimal("0.00")

    def test_kobe_precision_rounds_half_up(self):
        # 999.99 × 24% × 3/12 = 59.9994 → 60.00 (ROUND_HALF_UP)
        assert compute_flat_interest(Decimal("999.99"), 24, 3) == Decimal("60.00")
        # 999.90 × 24% × 3/12 = 59.994 → 59.99
        assert compute_flat_interest(Decimal("999.90"), 24, 3) == Decimal("59.99")


class TestDecliningBalance:
    def test_schedule_totals_exact(self):
        principal = Decimal("100000")
        lines = compute_declining_schedule(principal, 24, 12)
        principal_total = sum(l["principal_due"] for l in lines)
        assert principal_total == principal  # exact, no lost kobo
        assert len(lines) == 12

    def test_interest_decreases(self):
        lines = compute_declining_schedule(Decimal("50000"), 30, 6)
        interests = [l["interest_due"] for l in lines]
        assert interests == sorted(interests, reverse=True)

    def test_final_line_absorbs_rounding(self):
        lines = compute_declining_schedule(Decimal("333.33"), 25, 7)
        assert sum(l["principal_due"] for l in lines) == Decimal("333.33")


class TestScheduleGeneration:
    def test_monthly_real_calendar_dates(self):
        schedule = compute_schedule(
            principal=50000,
            annual_rate_percent=24,
            term_months=4,
            interest_method="FLAT",
            first_payment_date=date(2026, 1, 31),
        )
        assert [s["due_date"] for s in schedule] == [
            date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)
        ]
        # Flat interest split equally: total = 50000 × 24% × 4/12 = 4000
        assert sum(s["interest_due"] for s in schedule) == Decimal("4000.00")

    def test_total_repayable_consistent(self):
        schedule = compute_schedule(
            principal=25000, annual_rate_percent=26, term_months=3,
            interest_method="FLAT", first_payment_date=date.today(),
        )
        total = compute_total_repayable(schedule)
        assert total == Decimal("25000") + Decimal("1625.00")

    def test_unsupported_method_rejected(self):
        with pytest.raises(ValueError):
            compute_schedule(
                principal=1000, annual_rate_percent=10, term_months=2,
                interest_method="COMPOUND_MAGIC", first_payment_date=date.today(),
            )


class TestAllocation:  # spec §41 deterministic order
    def test_penalty_first(self):
        result = allocate_repayment(
            amount=100,
            penalties_due=20, fees_due=10, interest_due=30, principal_due=40,
        )
        assert result["PENALTY"] == Decimal("20.00")
        assert result["FEES"] == Decimal("10.00")
        assert result["INTEREST"] == Decimal("30.00")
        assert result["PRINCIPAL"] == Decimal("40.00")
        assert result["UNAPPLIED"] == Decimal("0.00")

    def test_partial_payment_covers_penalty_and_fees_first(self):
        result = allocate_repayment(
            amount=25, penalties_due=20, fees_due=10, interest_due=30, principal_due=40
        )
        assert result["PENALTY"] == Decimal("20.00")
        assert result["FEES"] == Decimal("5.00")
        assert result["INTEREST"] == Decimal("0.00")
        assert result["PRINCIPAL"] == Decimal("0.00")

    def test_overpayment_captured_as_unapplied(self):
        result = allocate_repayment(
            amount=200, penalties_due=20, fees_due=10, interest_due=30, principal_due=40
        )
        assert result["UNAPPLIED"] == Decimal("100.00")

    def test_custom_order_respected(self):
        result = allocate_repayment(
            amount=50, penalties_due=20, fees_due=10, interest_due=30, principal_due=40,
            order=["PRINCIPAL", "INTEREST", "FEES", "PENALTY"],
        )
        assert result["PRINCIPAL"] == Decimal("40.00")
        assert result["INTEREST"] == Decimal("10.00")
        assert result["PENALTY"] == Decimal("0.00")


class TestEligibility:
    def test_unverified_kyc_blocks_loan(self, customer):
        product = make_loan_product()
        result = check_eligibility(customer, product, 50000, 6)
        assert not result["eligible"]
        assert any("KYC" in r or "verification" in r for r in result["reasons"])

    def test_out_of_range_amount(self, verified_customer):
        product = make_loan_product()
        result = check_eligibility(verified_customer, product, 999999999, 6)
        assert not result["eligible"]

    def test_active_loan_blocks_second(self, verified_customer):
        product = make_loan_product()
        Loan.objects.create(
            reference="RF-LON-TEST-000001",
            application=_make_application(verified_customer),
            customer=verified_customer,
            product=product,
            principal=Decimal("10000"),
            interest_rate=Decimal("24"),
            term_months=6,
            outstanding_principal=Decimal("10000"),
            status=Loan.Status.ACTIVE,
        )
        result = check_eligibility(verified_customer, product, 20000, 6)
        assert not result["eligible"]


def _make_application(customer):
    from apps.loans.models import LoanApplication

    product = make_loan_product()
    return LoanApplication.objects.create(
        reference="RF-LAP-TEST-000001",
        customer=customer,
        product=product,
        product_config=product.current_config(),
        amount_requested=Decimal("50000"),
        term_months=6,
        state=LoanApplication.State.SUBMITTED,
    )


class TestLoanJourney:  # spec §200
    @pytest.fixture
    def application(self, db):
        customer = make_customer("+2348033330001")
        verify_kyc(customer)
        return create_loan_application(
            customer=customer,
            product_code="TRADER",
            amount=Decimal("50000"),
            term_months=6,
            purpose="Stock the shop",
        )

    @pytest.fixture
    def officer(self, db):
        from apps.accounts.services import grant_role
        from apps.accounts.models import User

        user = User.objects.create_user(
            phone="+2348044440001", password="Officer#2026", first_name="Loan", last_name="Officer"
        )
        grant_role(user, "LOAN_OFFICER")
        return user

    def test_full_journey_to_repayment(self, application, officer):
        # assessment ran automatically on submission
        assert application.assessment is not None
        assert application.assessment.decision in ("APPROVE", "REVIEW", "REJECT")
        assert application.state == LoanApplication.State.SUBMITTED

        # review → approve → offer
        approve_application(application, approver=officer, reason="good history")
        assert application.state == LoanApplication.State.OFFERED
        offer = application.offer
        assert offer.total_repayable == Decimal("56000.00")  # 50k + 6k flat interest

        # accept
        accept_offer(application, customer=application.customer)
        assert application.state == LoanApplication.State.ACCEPTED

        # disburse → ledger posting
        loan = disburse_loan(application, disbursed_by=officer)
        assert loan.status == Loan.Status.ACTIVE
        assert loan.repayment_schedule.count() == 6
        assert loan.ledger_transaction.status == "POSTED"

        # repay first installment: 50000/6 principal + 1000 interest ≈ 9333.33
        first = loan.repayment_schedule.get(sequence=1)
        amount = first.total_due
        payment, _ = initialize_payment(
            customer=application.customer,
            purpose="LOAN_REPAYMENT",
            amount=amount,
            target={"loan_id": str(loan.pk)},
            idempotency_key="repay-1",
        )
        settled = settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=amount,
            currency="NGN",
        )
        loan.refresh_from_db()
        first.refresh_from_db()
        assert first.status == RepaymentScheduleItem.Status.PAID
        assert loan.outstanding_principal < Decimal("50000")
        # Ledger holds the disbursement + repayment postings
        assert loan.ledger_transaction.total_debits() == Decimal("50000.00")

    def test_rejection_reason_required(self, application, officer):
        with pytest.raises(ValidationFailed, match="reason"):
            approve_application(application, approver=officer, reason="")

    def test_reject_application(self, application, officer):
        application = reject_application(
            application, reviewer=officer, reason="insufficient history"
        )
        assert application.state == LoanApplication.State.REJECTED
        assert application.rejection_reason == "insufficient history"

    def test_cannot_disburse_before_acceptance(self, application, officer):
        with pytest.raises(InvalidStateTransition):
            disburse_loan(application, disbursed_by=officer)

    def test_cannot_disburse_twice(self, application, officer):
        from apps.core.errors import Conflict

        approve_application(application, approver=officer, reason="ok")
        accept_offer(application, customer=application.customer)
        disburse_loan(application, disbursed_by=officer)
        with pytest.raises(Conflict):
            disburse_loan(application, disbursed_by=officer)


class TestPenalties:
    def test_late_penalty_applied_once(self, db):
        from apps.loans.models import RepaymentScheduleItem

        customer = make_customer("+2348033330002")
        verify_kyc(customer)
        from apps.accounts.services import grant_role
        from apps.accounts.models import User

        officer = User.objects.create_user(phone="+2348044440002", password="Officer#2026")
        grant_role(officer, "LOAN_OFFICER")
        application = create_loan_application(
            customer=customer, product_code="TRADER",
            amount=Decimal("30000"), term_months=3, purpose="stock",
        )
        approve_application(application, approver=officer, reason="ok")
        accept_offer(application, customer=customer)
        loan = disburse_loan(application, disbursed_by=officer)

        # Make first installment overdue
        first = loan.repayment_schedule.get(sequence=1)
        first.due_date = date.today() - timedelta(days=10)
        first.status = RepaymentScheduleItem.Status.DUE
        first.save()

        apply_late_penalties()
        count_after_first = loan.penalties.count()
        assert count_after_first == 1

        apply_late_penalties()  # idempotent
        assert loan.penalties.count() == count_after_first
