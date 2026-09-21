"""The double-entry ledger (spec §14, §15, §16) — the most important subsystem.

Guarantees:
  - sum(debits) == sum(credits) enforced BEFORE posting, and re-asserted
    by tests after every posting (spec §82)
  - POSTED transactions and their entries are immutable (§3.1)
  - corrections happen only through reversal transactions (§3.1)
  - balance is a transactionally-consistent projection derived from
    entries — never blindly incremented (§3.2)
  - idempotency keys are DB-unique; replays return the original (§3.5)
  - concurrent posting locks account rows (§57)
  - Decimal money only; explicit currency on every amount (§3.3, §3.4)
"""

from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel


class LedgerAccount(UUIDModel):
    """An account in the double-entry ledger.

    Customer savings, loan receivables, agent float, settlement, income
    and expense accounts are all LedgerAccounts. Financial products
    reference them; nothing outside the ledger ever mutates a balance.
    """

    class Type(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FROZEN = "FROZEN", "Frozen"
        CLOSED = "CLOSED", "Closed"

    code = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=10, choices=Type.choices)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    # Ledger-backed balance projection (§3.2). Updated ONLY by the posting
    # engine inside the posting transaction, in lockstep with entries.
    balance = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0.00"))
    currency_of_balance = models.CharField(max_length=3, default="NGN")
    allow_negative = models.BooleanField(default=False)
    holder_customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    holder_agent = models.ForeignKey(
        "agents.Agent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    last_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["type", "status"])]

    def __str__(self) -> str:
        return f"{self.code} ({self.type})"

    def computed_balance(self) -> Decimal:
        """Authoritative recomputation from entries (audit/verification)."""
        debits = Decimal("0")
        credits = Decimal("0")
        for entry in self.entries.all():
            if entry.direction == LedgerEntry.Direction.DEBIT:
                debits += entry.amount
            else:
                credits += entry.amount
        if self.type in (LedgerAccount.Type.ASSET, LedgerAccount.Type.EXPENSE):
            return debits - credits
        return credits - debits


class LedgerTransaction(UUIDModel):
    """A balanced set of entries moved between accounts (§14, §15)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        VALIDATING = "VALIDATING", "Validating"
        POSTED = "POSTED", "Posted"
        REJECTED = "REJECTED", "Rejected"
        REVERSED = "REVERSED", "Reversed"

    class Type(models.TextChoices):
        SAVINGS_DEPOSIT = "SAVINGS_DEPOSIT", "Savings deposit"
        SAVINGS_PAYOUT = "SAVINGS_PAYOUT", "Savings payout"
        AGENT_CASH_COLLECTION = "AGENT_CASH_COLLECTION", "Agent cash collection"
        AGENT_PAYOUT = "AGENT_PAYOUT", "Agent customer payout"
        AGENT_SETTLEMENT = "AGENT_SETTLEMENT", "Agent settlement"
        COMMISSION = "COMMISSION", "Commission"
        LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan disbursement"
        LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
        ADJUSTMENT = "ADJUSTMENT", "Manual adjustment"
        REVERSAL = "REVERSAL", "Reversal"
        OPENING = "OPENING", "Opening balance"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    transaction_type = models.CharField(max_length=24, choices=Type.choices, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    currency = models.CharField(max_length=3, default="NGN")
    description = models.CharField(max_length=250, blank=True, default="")
    external_reference = models.CharField(max_length=120, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )
    posted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_ledger_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["transaction_type", "-posted_at"]),
        ]

    def __str__(self) -> str:
        return self.reference

    # -- Immutability (§3.1) ------------------------------------------------
    IMMUTABLE_FIELDS = {
        "reference", "transaction_type", "currency", "idempotency_key",
        "created_by_id", "posted_at", "reversal_of_id",
    }

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old = LedgerTransaction.objects.filter(pk=self.pk).values(
                "reference", "transaction_type", "currency", "idempotency_key",
                "created_by_id", "posted_at", "reversal_of_id",
            ).first()
            if old:
                for field, value in old.items():
                    if getattr(self, field) != value:
                        raise RuntimeError(
                            f"LedgerTransaction.{field} is immutable after creation."
                        )
        return super().save(*args, **kwargs)

    @property
    def is_posted(self) -> bool:
        return self.status == LedgerTransaction.Status.POSTED

    def total_debits(self) -> Decimal:
        return sum(
            (e.amount for e in self.entries.all() if e.direction == LedgerEntry.Direction.DEBIT),
            Decimal("0"),
        )

    def total_credits(self) -> Decimal:
        return sum(
            (e.amount for e in self.entries.all() if e.direction == LedgerEntry.Direction.CREDIT),
            Decimal("0"),
        )


class LedgerEntry(UUIDModel):
    """A single debit or credit line of a transaction. Immutable once posted."""

    class Direction(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    transaction = models.ForeignKey(
        LedgerTransaction, on_delete=models.PROTECT, related_name="entries"
    )
    account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, related_name="entries"
    )
    direction = models.CharField(max_length=6, choices=Direction.choices)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0), name="ledger_entry_positive_amount"
            ),
            models.CheckConstraint(
                check=models.Q(direction="DEBIT") | models.Q(direction="CREDIT"),
                name="ledger_entry_direction",
            ),
        ]
        indexes = [models.Index(fields=["account", "-created_at"])]

    def save(self, *args, **kwargs):
        if self._state.adding is False and self.transaction.status == LedgerTransaction.Status.POSTED:
            raise RuntimeError("LedgerEntry rows are immutable once the transaction is posted.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: D102
        if self.transaction.status == LedgerTransaction.Status.POSTED:
            raise RuntimeError("Posted ledger entries can never be deleted.")
        return super().delete(*args, **kwargs)


class AccountingPeriod(UUIDModel):
    name = models.CharField(max_length=40, unique=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=8, default="OPEN")  # OPEN / CLOSED

    class Meta:
        ordering = ["-starts_at"]


class BalanceSnapshot(UUIDModel):
    """Periodic point-in-time balances — audit evidence (spec §14)."""

    account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, related_name="snapshots"
    )
    as_of = models.DateTimeField(default=timezone.now, db_index=True)
    balance = models.DecimalField(max_digits=19, decimal_places=2)
    entry_count = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["account", "as_of"], name="uniq_snapshot_acct_time")
        ]


class LedgerBatch(UUIDModel):
    """Bulk operations (opening balances, migrations of legacy data)."""

    reference = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=250, blank=True, default="")
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
