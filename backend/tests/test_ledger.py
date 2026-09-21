"""Ledger invariant tests (spec §14–§16, §82, §205) — the most critical suite."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.core.errors import (
    Conflict,
    IdempotencyConflict,
    InvalidStateTransition,
    ValidationFailed,
)
from apps.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from apps.ledger.services import (
    EntrySpec,
    create_account,
    ensure_core_accounts,
    post_transaction,
    reverse_transaction,
    verify_balances,
)


@pytest.fixture(autouse=True)
def _accounts(db):
    ensure_core_accounts()


def simple_entries(amount="1000"):
    return [
        EntrySpec(account="SETTLEMENT", direction="DEBIT", amount=amount),
        EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount=amount),
    ]


class TestDoubleEntryInvariants:
    def test_posted_transaction_is_balanced(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="test", entries=simple_entries("500")
        )
        assert txn.status == LedgerTransaction.Status.POSTED
        assert txn.total_debits() == txn.total_credits() == Decimal("500.00")

    def test_unbalanced_transaction_rejected(self):
        entries = [
            EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="100"),
            EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="99"),
        ]
        with pytest.raises(ValidationFailed, match="not balanced"):
            post_transaction(txn_type="SAVINGS_DEPOSIT", description="bad", entries=entries)

    def test_single_entry_rejected(self):
        with pytest.raises(ValidationFailed):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="one-sided",
                entries=[EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="10")],
            )

    def test_zero_amount_rejected(self):
        with pytest.raises(ValidationFailed):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="zero",
                entries=[
                    EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="0"),
                    EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="0"),
                ],
            )

    def test_negative_amount_rejected(self):
        with pytest.raises(ValidationFailed):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="neg",
                entries=[
                    EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="-5"),
                    EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="-5"),
                ],
            )

    def test_unknown_account_rejected(self):
        with pytest.raises(ValidationFailed, match="does not exist"):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="ghost",
                entries=[
                    EntrySpec(account="NOPE", direction="DEBIT", amount="1"),
                    EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="1"),
                ],
            )

    def test_currency_mismatch_rejected(self):
        with pytest.raises(ValidationFailed, match="holds"):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="usd into ngn",
                currency="USD",
                entries=[
                    EntrySpec(account="SETTLEMENT", direction="DEBIT", amount="1"),
                    EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount="1"),
                ],
            )

    def test_balance_projection_matches_entries(self):
        post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="a", entries=simple_entries("123.45")
        )
        post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="b", entries=simple_entries("77.55")
        )
        pool = LedgerAccount.objects.get(code="SAVINGS_POOL")
        assert pool.balance == Decimal("201.00")
        assert pool.computed_balance() == pool.balance
        verify_balances()  # must not raise


class TestImmutability:  # spec §3.1
    def test_posted_transaction_reference_immutable(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="x", entries=simple_entries("10")
        )
        txn.reference = "RF-XXX-000000-000001"
        with pytest.raises(RuntimeError, match="immutable"):
            txn.save()

    def test_posted_entry_cannot_be_deleted(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="x", entries=simple_entries("10")
        )
        entry = txn.entries.first()
        with pytest.raises(RuntimeError):
            entry.delete()

    def test_audit_events_append_only(self):
        from apps.audit.models import AuditEvent

        event = AuditEvent.objects.create(
            action="CREATE", resource_type="test", resource_id="1"
        )
        with pytest.raises(RuntimeError):
            event.delete()
        event.reason = "edit attempt"
        with pytest.raises(RuntimeError):
            event.save()


class TestReversal:  # spec §205
    def test_reversal_net_zero(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT",
            description="original",
            entries=simple_entries("10000"),
        )
        reversal = reverse_transaction(txn, reason="test reversal")
        pool = LedgerAccount.objects.get(code="SAVINGS_POOL")
        assert pool.balance == Decimal("0.00")
        assert reversal.reversal_of_id == txn.pk
        assert reversal.transaction_type == LedgerTransaction.Type.REVERSAL
        # Both remain auditable
        assert LedgerTransaction.objects.filter(pk=txn.pk).exists()
        assert LedgerEntry.objects.filter(transaction=txn).count() == 2

    def test_double_reversal_rejected(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="x", entries=simple_entries("10")
        )
        reverse_transaction(txn, reason="first")
        with pytest.raises(Conflict, match="already been reversed"):
            reverse_transaction(txn, reason="second")

    def test_reversal_requires_reason(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="x", entries=simple_entries("10")
        )
        with pytest.raises(ValidationFailed, match="reason"):
            reverse_transaction(txn, reason="")


class TestIdempotency:  # spec §3.5
    def test_same_key_returns_same_transaction(self):
        first = post_transaction(
            txn_type="SAVINGS_DEPOSIT",
            description="once",
            entries=simple_entries("50"),
            idempotency_key="key-1",
        )
        second = post_transaction(
            txn_type="SAVINGS_DEPOSIT",
            description="replay",
            entries=simple_entries("50"),
            idempotency_key="key-1",
        )
        assert first.pk == second.pk
        pool = LedgerAccount.objects.get(code="SAVINGS_POOL")
        assert pool.balance == Decimal("50.00")  # exactly once

    def test_same_key_different_details_rejected(self):
        post_transaction(
            txn_type="SAVINGS_DEPOSIT",
            description="original",
            entries=simple_entries("50"),
            idempotency_key="key-2",
        )
        with pytest.raises(IdempotencyConflict):
            post_transaction(
                txn_type="SAVINGS_DEPOSIT",
                description="different amount",
                entries=simple_entries("60"),
                idempotency_key="key-2",
            )

    def test_unique_constraint_at_db_level(self):
        post_transaction(
            txn_type="SAVINGS_DEPOSIT",
            description="db",
            entries=simple_entries("10"),
            idempotency_key="uniq-1",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LedgerTransaction.objects.create(
                    reference="RF-LED-TEST-000001",
                    transaction_type="SAVINGS_DEPOSIT",
                    status="POSTED",
                    idempotency_key="uniq-1",
                )


class TestNegativeBalanceGuard:  # spec §82
    def test_liability_cannot_go_negative(self):
        with pytest.raises(ValidationFailed, match="cannot go negative"):
            post_transaction(
                txn_type="SAVINGS_PAYOUT",
                description="overdraft attempt",
                entries=[
                    EntrySpec(account="SAVINGS_POOL", direction="DEBIT", amount="100"),
                    EntrySpec(account="SETTLEMENT", direction="CREDIT", amount="100"),
                ],
            )

    def test_frozen_account_rejected(self):
        create_account(code="TEST_FROZEN", name="Frozen", type="ASSET")
        acct = LedgerAccount.objects.get(code="TEST_FROZEN")
        acct.status = LedgerAccount.Status.FROZEN
        acct.save()
        with pytest.raises(InvalidStateTransition, match="not active"):
            post_transaction(
                txn_type="ADJUSTMENT",
                description="to frozen",
                entries=[
                    EntrySpec(account="TEST_FROZEN", direction="DEBIT", amount="1"),
                    EntrySpec(account="SETTLEMENT", direction="CREDIT", amount="1"),
                ],
            )


class TestReferences:
    def test_reference_format(self):
        txn = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="ref", entries=simple_entries("5")
        )
        assert txn.reference.startswith("RF-LED-")
        parts = txn.reference.split("-")
        assert len(parts) == 4 and parts[0] == "RF" and len(parts[2]) == 8

    def test_references_unique(self):
        t1 = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="r1", entries=simple_entries("5")
        )
        t2 = post_transaction(
            txn_type="SAVINGS_DEPOSIT", description="r2", entries=simple_entries("5")
        )
        assert t1.reference != t2.reference


class TestOpeningBalances:
    def test_opening_balance_posts_against_equity(self):
        create_account(
            code="TEST_OPEN", name="Opening test", type="ASSET", opening_balance=Decimal("500")
        )
        acct = LedgerAccount.objects.get(code="TEST_OPEN")
        assert acct.balance == Decimal("500.00")
        equity = LedgerAccount.objects.get(code="OPENING_EQUITY")
        # Asset +500 balanced by equity credit +500 (assets = equity)
        assert equity.computed_balance() == Decimal("500.00")
