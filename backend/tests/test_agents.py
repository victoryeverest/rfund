"""Agent system tests (spec §29–§34, §58, §146)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.agents import services as agent_services
from apps.agents.models import Agent, AgentDevice, AgentTransaction
from apps.core.errors import (
    InsufficientFunds,
    InvalidStateTransition,
    LimitExceeded,
    ValidationFailed,
)
from apps.ledger.services import ensure_core_accounts, verify_balances
from apps.savings.services import create_savings_plan, ensure_default_products
from tests.factories import make_customer, verify_kyc


@pytest.fixture(autouse=True)
def _setup(db):
    ensure_core_accounts()
    ensure_default_products()


class TestCashCollection:
    def test_collection_posts_ledger_and_float(self, agent, customer):
        txn = agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("5000")
        )
        assert txn.status == AgentTransaction.Status.SUCCESS
        assert agent_services.agent_float_balance(agent) == Decimal("5000.00")
        verify_balances()

    def test_collection_creates_savings_contribution(self, agent, verified_customer):
        plan = create_savings_plan(
            customer=verified_customer,
            product_code="SAVE_FLEX",
            amount=Decimal("1000"),
            frequency="DAILY",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5),
        )
        txn = agent_services.agent_cash_collection(
            agent=agent,
            customer=verified_customer,
            amount=Decimal("1000"),
            purpose="SAVINGS_CONTRIBUTION",
            target={"plan_id": str(plan.pk)},
        )
        plan.refresh_from_db()
        assert plan.total_contributed == Decimal("1000.00")

    def test_idempotent_collection(self, agent, customer):
        t1 = agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("100"), idempotency_key="ag-1"
        )
        t2 = agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("100"), idempotency_key="ag-1"
        )
        assert t1.pk == t2.pk
        assert AgentTransaction.objects.count() == 1

    def test_single_txn_limit(self, agent, customer):
        with pytest.raises(LimitExceeded, match="single transaction"):
            agent_services.agent_cash_collection(
                agent=agent, customer=customer, amount=Decimal("60000")
            )

    def test_daily_limit_enforced(self, agent, customer):
        for i in range(4):
            agent_services.agent_cash_collection(
                agent=agent, customer=customer, amount=Decimal("50000")
            )
        with pytest.raises(LimitExceeded, match="Daily"):
            agent_services.agent_cash_collection(
                agent=agent, customer=customer, amount=Decimal("10000")
            )


class TestAgentPayout:
    def test_payout_reduces_pool(self, agent, customer):
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("3000")
        )
        txn = agent_services.agent_customer_payout(
            agent=agent, customer=customer, amount=Decimal("2000")
        )
        assert txn.status == AgentTransaction.Status.SUCCESS
        from apps.ledger.models import LedgerAccount

        pool = LedgerAccount.objects.get(code="SAVINGS_POOL")
        assert pool.balance == Decimal("1000.00")

    def test_payout_cannot_overdraw_pool(self, agent, customer):
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("1000")
        )
        with pytest.raises(InsufficientFunds):
            agent_services.agent_customer_payout(
                agent=agent, customer=customer, amount=Decimal("5000")
            )


class TestDeviceSecurity:  # spec §30
    def test_disabled_device_cannot_transact(self, agent, customer):
        device = agent_services.register_device(agent, fingerprint="dev-123")
        device.disable()
        with pytest.raises(InvalidStateTransition, match="disabled"):
            agent_services.agent_cash_collection(
                agent=agent, customer=customer, amount=Decimal("100"), device=device
            )

    def test_device_fingerprint_unique_per_agent(self, agent, customer):
        agent_services.register_device(agent, fingerprint="dev-456")
        other = make_customer("+2348011190001").user
        from apps.agents.services import register_agent

        other_agent = register_agent(
            user=other, territory_code=agent.territory.code
        )
        from apps.core.errors import Conflict

        with pytest.raises(Conflict):
            agent_services.register_device(other_agent, fingerprint="dev-456")


class TestSettlements:  # spec §33
    def test_settlement_workflow(self, agent, customer, staff_user):
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("10000")
        )
        settlement = agent_services.request_agent_settlement(agent)
        assert settlement.status == "SETTLEMENT_REQUESTED"
        agent_services.review_agent_settlement(settlement, reviewer=staff_user, approve=True)
        assert settlement.status == "UNDER_REVIEW"
        agent_services.approve_agent_settlement(settlement, approver=staff_user)
        settlement.refresh_from_db()
        assert settlement.status == "SETTLED"
        assert settlement.ledger_transaction.status == "POSTED"
        assert agent_services.agent_float_balance(agent) == Decimal("0.00")
        verify_balances()

    def test_settlement_cannot_exceed_float(self, agent, customer):
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("5000")
        )
        with pytest.raises(ValidationFailed, match="exceeds"):
            agent_services.request_agent_settlement(agent, amount=Decimal("999999"))

    def test_settlement_requires_review_before_approval(self, agent, customer, staff_user):
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("1000")
        )
        settlement = agent_services.request_agent_settlement(agent)
        with pytest.raises(InvalidStateTransition):
            agent_services.approve_agent_settlement(settlement, approver=staff_user)


class TestCommission:
    def test_commission_accrues_and_pays_through_ledger(self, agent, customer, staff_user):
        from apps.agents.models import CommissionRule

        CommissionRule.objects.create(
            name="1% collections",
            txn_type="CASH_COLLECTION",
            basis="PERCENT",
            rate=Decimal("1.0000"),
        )
        agent_services.agent_cash_collection(
            agent=agent, customer=customer, amount=Decimal("10000")
        )
        accrued = agent.commissions.filter(status="ACCRUED").count()
        assert accrued == 1
        paid = agent_services.settle_commissions(agent, settled_by=staff_user)
        assert paid == Decimal("100.00")
        assert not agent.commissions.filter(status="ACCRUED").exists()
        verify_balances()  # commission posted via ledger, not a balance hack (§146)


class TestAgentStatus:
    def test_suspended_agent_cannot_collect(self, agent, customer, staff_user):
        agent_services.set_agent_status(agent, "SUSPENDED", actor=staff_user, reason="audit")
        with pytest.raises(InvalidStateTransition):
            agent_services.agent_cash_collection(
                agent=agent, customer=customer, amount=Decimal("100")
            )
