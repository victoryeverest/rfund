"""Concurrency tests (spec §58, §203) — parallel money movement.

Uses TransactionTestCase with real commits so threads observe each
other's writes. PostgreSQL provides true row-level locking; SQLite
sandbox runs use WAL + busy timeout for comparable behaviour.
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection, connections
from django.test import TransactionTestCase

from apps.agents import services as agent_services
from apps.core.errors import LimitExceeded
from apps.ledger.models import LedgerAccount, LedgerTransaction
from apps.ledger.services import EntrySpec, ensure_core_accounts, post_transaction, verify_balances
from apps.payments import services as payment_services
from apps.payments.models import Payment
from apps.savings.services import create_savings_plan, ensure_default_products
from tests.factories import make_agent, make_customer, verify_kyc


def thread_safe(fn):
    """Close worker-thread DB connections so teardown can drop the DB."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            connections.close_all()

    return wrapper


class LedgerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        ensure_core_accounts()
        ensure_default_products()
        self._enable_sqlite_wal()

    @staticmethod
    def _enable_sqlite_wal():
        if not connection.settings_dict["ENGINE"].endswith("sqlite3"):
            return
        db_name = connection.settings_dict["NAME"]
        raw = sqlite3.connect(db_name, timeout=60)
        try:
            raw.execute("PRAGMA journal_mode=WAL;")
            raw.execute("PRAGMA busy_timeout=60000;")
        finally:
            raw.close()

    def test_parallel_postings_all_balanced(self):  # spec §203
        """20 concurrent postings: every one balanced, balance exact."""

        @thread_safe
        def post(i):
            return post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description=f"concurrent {i}",
                entries=[
                    EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="100"),
                    EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="100"),
                ],
                idempotency_key=f"conc-{i}",
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(post, range(20)))
        self.assertEqual(len(results), 20)
        self.assertEqual(len({r.pk for r in results}), 20)  # 20 distinct txns
        pool_acct = LedgerAccount.objects.get(code="SAVINGS_POOL")
        self.assertEqual(pool_acct.balance, Decimal("2000.00"))  # 20 × 100 exactly
        self.assertEqual(pool_acct.computed_balance(), pool_acct.balance)

    def test_same_idempotency_key_under_concurrency(self):
        """Two threads, one key: exactly one financial effect."""

        @thread_safe
        def post(_i):
            try:
                return post_transaction(
                    txn_type="SAVINGS_DEPOSIT",
                    description="race",
                    entries=[
                        EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="500"),
                        EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="500"),
                    ],
                    idempotency_key="race-key",
                )
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(post, range(2)))
        self.assertEqual(
            LedgerTransaction.objects.filter(idempotency_key="race-key").count(), 1
        )
        pool_acct = LedgerAccount.objects.get(code="SAVINGS_POOL")
        self.assertEqual(pool_acct.balance, Decimal("500.00"))

    def test_duplicate_webhook_storm(self):  # spec §202
        """10 concurrent webhook deliveries of the same event."""

        @thread_safe
        def process(_):
            try:
                return payment_services.process_webhook_event(event)
            except Exception:
                return None

        from integrations.payments.base import get_payment_provider

        customer = make_customer("+2348077770001")
        verify_kyc(customer)
        payment, _ = payment_services.initialize_payment(
            customer=customer,
            purpose="ACCOUNT_FUNDING",
            amount=Decimal("1500"),
            idempotency_key="storm-1",
        )
        local = get_payment_provider("local")
        event = payment_services.ingest_webhook(
            provider_code="local",
            event_id="evt-storm",
            event_type="charge.success",
            payload=local.mark_success(payment.provider_reference),
            signature_valid=True,
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(process, range(10)))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        # exactly one ledger posting for this payment
        self.assertEqual(
            LedgerTransaction.objects.filter(
                idempotency_key=f"payment:{payment.reference}"
            ).count(),
            1,
        )

    def test_agent_limit_race(self):  # spec §58
        """Concurrent collections cannot exceed the daily limit."""

        @thread_safe
        def collect(i):
            try:
                return agent_services.agent_cash_collection(
                    agent=agent,
                    customer=customer,
                    amount=Decimal("50000"),  # daily limit 200000 → max 4
                    idempotency_key=f"race-{i}",
                )
            except LimitExceeded:
                return "rejected"

        agent = make_agent("+2348077770002")
        customer = make_customer("+2348077770003")
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(collect, range(6)))
        accepted = [r for r in results if r != "rejected"]
        rejected = [r for r in results if r == "rejected"]
        self.assertLessEqual(len(accepted), 4)
        self.assertGreaterEqual(len(rejected), 2)
        total = sum(t.amount for t in accepted)
        self.assertLessEqual(total, Decimal("200000"))

    def test_concurrent_savings_contributions(self):
        """Four simultaneous payments into one plan all land (serialized)."""

        @thread_safe
        def pay(i):
            payment, _ = payment_services.initialize_payment(
                customer=customer,
                purpose="SAVINGS_CONTRIBUTION",
                amount=Decimal("200"),
                target={"plan_id": str(plan.pk)},
                idempotency_key=f"plan-race-{i}",
            )
            return payment_services.settle_payment(
                payment,
                provider_reference=payment.provider_reference,
                amount=Decimal("200"),
                currency="NGN",
            )

        customer = make_customer("+2348077770004")
        verify_kyc(customer)
        plan = create_savings_plan(
            customer=customer,
            product_code="SAVE_FLEX",
            amount=Decimal("200"),
            frequency="DAILY",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5),
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(pay, range(4)))
        plan.refresh_from_db()
        self.assertEqual(plan.total_contributed, Decimal("800.00"))
        verify_balances()
