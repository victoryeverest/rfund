"""Savings service tests: plans, contributions, goals, payouts."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.errors import InsufficientFunds, InvalidStateTransition, ValidationFailed
from apps.ledger.services import ensure_core_accounts, verify_balances
from apps.payments.models import Payment
from apps.payments.services import initialize_payment, settle_payment
from apps.savings.models import SavingsGoal, SavingsPlan, SavingsScheduleItem
from apps.savings.services import (
    cancel_savings_plan,
    create_goal,
    create_savings_plan,
    ensure_default_products,
    request_savings_payout,
    process_savings_payout,
    refresh_schedule_statuses,
)
from tests.factories import make_savings_product, verify_kyc


@pytest.fixture(autouse=True)
def _setup(db):
    ensure_core_accounts()
    ensure_default_products()


def make_plan(customer, amount="1000", frequency="DAILY", days=10, start=None):
    start = start or date.today()
    return create_savings_plan(
        customer=customer,
        product_code="SAVE_FLEX",
        amount=Decimal(amount),
        frequency=frequency,
        start_date=start,
        end_date=start + timedelta(days=days),
    )


def make_plan_backdated(customer, days=5, back=3):
    """Plans with history for due/missed status tests."""
    start = date.today() - timedelta(days=back)
    return create_savings_plan(
        customer=customer,
        product_code="SAVE_FLEX",
        amount=Decimal("1000"),
        frequency="DAILY",
        start_date=start,
        end_date=start + timedelta(days=days),
        allow_past_start=True,
    )


class TestPlanCreation:
    def test_creates_calendar_schedule(self, customer):
        plan = make_plan(customer, days=5)
        assert plan.status == SavingsPlan.Status.ACTIVE
        assert plan.schedule_items.count() == 6  # inclusive start..end
        assert plan.reference.startswith("RF-SAV-")

    def test_amount_bounds_enforced(self, customer):
        with pytest.raises(ValidationFailed, match="between"):
            make_plan(customer, amount="50")  # below min 100

    def test_past_start_rejected(self, customer):
        with pytest.raises(ValidationFailed, match="past"):
            make_plan(customer, start=date.today() - timedelta(days=1))

    def test_end_before_start_rejected(self, customer):
        with pytest.raises(ValidationFailed):
            create_savings_plan(
                customer=customer,
                product_code="SAVE_FLEX",
                amount=Decimal("1000"),
                frequency="DAILY",
                start_date=date.today(),
                end_date=date.today() - timedelta(days=1),
            )

    def test_product_version_snapshot_stored(self, customer):  # spec §94
        plan = make_plan(customer)
        assert plan.product_config["code"] == "SAVE_FLEX"
        assert "min_contribution" in plan.product_config


class TestContributions:
    def test_payment_settles_into_plan(self, verified_customer):
        plan = make_plan(verified_customer, days=3)
        payment, _url = initialize_payment(
            customer=verified_customer,
            purpose="SAVINGS_CONTRIBUTION",
            amount=Decimal("1000"),
            target={"plan_id": str(plan.pk)},
            idempotency_key="contrib-1",
        )
        settled = settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=Decimal("1000"),
            currency="NGN",
            method="CARD",
        )
        assert settled.status == Payment.Status.SUCCESS
        plan.refresh_from_db()
        assert plan.total_contributed == Decimal("1000.00")
        assert plan.schedule_items.filter(status="PAID").count() == 1

    def test_ledger_backed_balance_updates(self, verified_customer):
        from apps.ledger.models import LedgerAccount

        make_plan(verified_customer, days=3)
        payment, _ = initialize_payment(
            customer=verified_customer,
            purpose="SAVINGS_CONTRIBUTION",
            amount=Decimal("500"),
            target={"plan_id": str(SavingsPlan.objects.first().pk)},
            idempotency_key="contrib-2",
        )
        settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=Decimal("500"),
            currency="NGN",
        )
        pool = LedgerAccount.objects.get(code="SAVINGS_POOL")
        assert pool.balance == Decimal("500.00")
        assert pool.balance == pool.computed_balance()
        verify_balances()

    def test_plan_completes_when_all_paid(self, verified_customer):
        plan = make_plan(verified_customer, days=1, amount="100")  # 2 items
        for i in range(2):
            payment, _ = initialize_payment(
                customer=verified_customer,
                purpose="SAVINGS_CONTRIBUTION",
                amount=Decimal("100"),
                target={"plan_id": str(plan.pk)},
                idempotency_key=f"complete-{i}",
            )
            settle_payment(
                payment,
                provider_reference=payment.provider_reference,
                amount=Decimal("100"),
                currency="NGN",
            )
        plan.refresh_from_db()
        assert plan.status == SavingsPlan.Status.COMPLETED


class TestCancellation:
    def test_cancel_marks_future_items_cancelled(self, customer):
        plan = make_plan(customer, days=10)
        plan = cancel_savings_plan(plan, actor=customer.user, reason="test")
        assert plan.status == SavingsPlan.Status.CANCELLED
        assert plan.schedule_items.filter(
            status=SavingsScheduleItem.Status.CANCELLED
        ).count() == plan.schedule_items.count()

    def test_cannot_cancel_twice(self, customer):
        plan = cancel_savings_plan(make_plan(customer), actor=customer.user)
        with pytest.raises(InvalidStateTransition):
            cancel_savings_plan(plan, actor=customer.user)


class TestGoals:
    def test_create_and_fund_goal(self, verified_customer):
        goal = create_goal(
            customer=verified_customer,
            name="Farm inputs",
            target_amount=Decimal("10000"),
        )
        payment, _ = initialize_payment(
            customer=verified_customer,
            purpose="GOAL_FUNDING",
            amount=Decimal("10000"),
            target={"goal_id": str(goal.pk)},
            idempotency_key="goal-1",
        )
        settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=Decimal("10000"),
            currency="NGN",
        )
        goal.refresh_from_db()
        assert goal.status == SavingsGoal.Status.COMPLETED
        assert goal.current_amount == Decimal("10000.00")

    def test_goal_validation(self, customer):
        with pytest.raises(ValidationFailed):
            create_goal(customer=customer, name="", target_amount=100)
        with pytest.raises(ValidationFailed):
            create_goal(customer=customer, name="X", target_amount=0)
        with pytest.raises(ValidationFailed):
            create_goal(
                customer=customer, name="X", target_amount=100,
                target_date=date.today() - timedelta(days=1),
            )


class TestPayouts:  # spec §156 money-movement safety
    def test_payout_of_completed_plan(self, verified_customer):
        plan = make_plan(verified_customer, days=1, amount="100")
        for i in range(2):
            payment, _ = initialize_payment(
                customer=verified_customer,
                purpose="SAVINGS_CONTRIBUTION",
                amount=Decimal("100"),
                target={"plan_id": str(plan.pk)},
                idempotency_key=f"pay-{i}",
            )
            settle_payment(
                payment,
                provider_reference=payment.provider_reference,
                amount=Decimal("100"),
                currency="NGN",
            )
        payout = request_savings_payout(plan, requested_by=verified_customer.user)
        assert payout.status == "REQUESTED"
        process_savings_payout(payout, approved_by=verified_customer.user)
        payout.refresh_from_db()
        assert payout.status == "PAID"
        plan.refresh_from_db()
        assert plan.total_contributed == Decimal("0.00")

    def test_early_payout_blocked_for_term_product(self, customer):
        from apps.savings.services import get_product

        plan = create_savings_plan(
            customer=customer,
            product_code="AJO_DAILY",
            amount=Decimal("500"),
            frequency="DAILY",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        with pytest.raises(InvalidStateTransition):
            request_savings_payout(plan, requested_by=customer.user)


class TestScheduledStatusRefresh:
    def test_due_and_missed_transitions(self, customer):
        plan = make_plan_backdated(customer)
        stats = refresh_schedule_statuses()
        assert stats["marked_due"] >= 1
        item = plan.schedule_items.order_by("sequence").first()
        assert item.status in (SavingsScheduleItem.Status.DUE, SavingsScheduleItem.Status.MISSED)

    def test_idempotent_refresh(self, customer):
        make_plan_backdated(customer)
        refresh_schedule_statuses()
        stats = refresh_schedule_statuses()  # second run must not double-count
        assert stats["marked_missed"] == 0 or stats["marked_due"] == 0
