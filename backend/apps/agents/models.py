"""Agent domain (spec §29–§34).

Agents collect cash for customer savings and pay out on request.
Every agent operation is a financial transaction through the ledger:
  collection: DR AGENT_FLOAT (liability owed to RFUND by agent rises via
              CASH_IN_HAND) — modelled per flow below.
Actual posting used (kept simple + balanced):
  Cash collection (agent collects for a customer's savings):
      DR CASH_IN_HAND   (asset: money physically with agent)
      CR SAVINGS_POOL   (liability: we owe the customer)
  Agent settlement (agent hands cash to RFUND):
      DR SETTLEMENT     (asset: money with payment partner/bank)
      CR CASH_IN_HAND   (asset: reduce agent-held cash)
  Customer payout via agent:
      DR SAVINGS_POOL   (liability falls)
      CR CASH_IN_HAND   (asset: agent holds less of our cash)
Agent float tracking records opening/closing per movement for
reconciliation (§32). Commissions post to COMMISSION_EXPENSE against
the agent's float account when settled.
"""

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel


class AgentTerritory(models.Model):
    code = models.CharField(max_length=20, primary_key=True)
    state = models.CharField(max_length=60)
    lga = models.CharField(max_length=80, blank=True, default="")
    communities = models.JSONField(default=list)

    def __str__(self) -> str:
        return self.code


class Agent(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DEACTIVATED = "DEACTIVATED", "Deactivated"

    agent_code = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.OneToOneField(
        "accounts.User", on_delete=models.PROTECT, related_name="agent_profile"
    )
    territory = models.ForeignKey(
        AgentTerritory, on_delete=models.PROTECT, related_name="agents"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    business_name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=16, blank=True, default="")
    supervisor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="supervised_agents"
    )
    onboarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["agent_code"]

    def __str__(self) -> str:
        return self.agent_code


class AgentDevice(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"

    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="devices")
    fingerprint = models.CharField(max_length=120, unique=True, db_index=True)
    device_name = models.CharField(max_length=120, blank=True, default="")
    os_version = models.CharField(max_length=40, blank=True, default="")
    app_version = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    last_seen = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def disable(self):
        self.status = self.Status.DISABLED
        self.save(update_fields=["status"])


class AgentLimit(UUIDModel):
    """Server-side limits (spec §29, §158). Race-safe enforcement in services."""

    agent = models.OneToOneField(Agent, on_delete=models.PROTECT, related_name="limits")
    single_transaction_limit = models.DecimalField(max_digits=19, decimal_places=2, default=50000)
    daily_cash_in_limit = models.DecimalField(max_digits=19, decimal_places=2, default=200000)
    daily_payout_limit = models.DecimalField(max_digits=19, decimal_places=2, default=100000)
    monthly_limit = models.DecimalField(max_digits=19, decimal_places=2, default=2000000)
    updated_at = models.DateTimeField(auto_now=True)


class AgentTransaction(UUIDModel):
    class Type(models.TextChoices):
        CASH_COLLECTION = "CASH_COLLECTION", "Cash collection"
        CUSTOMER_PAYOUT = "CUSTOMER_PAYOUT", "Customer payout"

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        VALIDATED = "VALIDATED", "Validated"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REVERSED = "REVERSED", "Reversed"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="transactions")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="agent_transactions"
    )
    txn_type = models.CharField(max_length=18, choices=Type.choices, db_index=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INITIATED)
    device = models.ForeignKey(
        AgentDevice, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    client_reference = models.CharField(max_length=120, blank=True, default="")
    idempotency_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    purpose = models.CharField(max_length=24, default="SAVINGS_CONTRIBUTION")
    target = models.JSONField(default=dict, blank=True)
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="agent_transactions",
    )
    failure_reason = models.CharField(max_length=250, blank=True, default="")
    performed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-performed_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0), name="agent_txn_positive_amount"
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_agent_txn_idempotency",
            ),
        ]
        indexes = [models.Index(fields=["agent", "-performed_at"])]


class AgentFloatMovement(UUIDModel):
    """Opening/closing per movement — reconciliation evidence (§32)."""

    class Direction(models.TextChoices):
        IN = "IN", "In (collections increase agent-held cash)"
        OUT = "OUT", "Out (payouts/settlements reduce it)"

    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="float_movements")
    transaction = models.OneToOneField(
        AgentTransaction, on_delete=models.PROTECT, related_name="float_movement", blank=True, null=True
    )
    settlement = models.ForeignKey(
        "AgentSettlement", null=True, blank=True, on_delete=models.PROTECT, related_name="float_movements"
    )
    direction = models.CharField(max_length=4, choices=Direction.choices)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    opening_balance = models.DecimalField(max_digits=19, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=19, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AgentSettlement(UUIDModel):
    """Agent hands collected cash to RFUND (§33)."""

    class Status(models.TextChoices):
        COLLECTED = "COLLECTED", "Collected"
        PENDING_SETTLEMENT = "PENDING_SETTLEMENT", "Pending settlement"
        SETTLEMENT_REQUESTED = "SETTLEMENT_REQUESTED", "Settlement requested"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        APPROVED = "APPROVED", "Approved"
        SETTLED = "SETTLED", "Settled"
        REJECTED = "REJECTED", "Rejected"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="settlements")
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    status = models.CharField(max_length=22, choices=Status.choices, default=Status.PENDING_SETTLEMENT)
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    settled_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="agent_settlements",
    )
    reason = models.TextField(blank=True, default="")
    requested_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class CommissionRule(UUIDModel):
    """Configurable commission (spec §146). Never hard-coded rates."""

    class Basis(models.TextChoices):
        PERCENT = "PERCENT", "Percent of transaction amount"
        FIXED = "FIXED", "Fixed amount per transaction"

    name = models.CharField(max_length=80)
    txn_type = models.CharField(max_length=18, blank=True, default="")  # "" = all
    basis = models.CharField(max_length=8, choices=Basis.choices, default="PERCENT")
    rate = models.DecimalField(max_digits=6, decimal_places=4)  # percent
    fixed_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    min_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=19, decimal_places=2, default=1000000)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    def compute(self, amount) -> "decimal.Decimal":
        from apps.core.money import money

        if not self.active:
            return money(0)
        if self.min_amount and amount < self.min_amount:
            return money(0)
        if self.max_amount and amount > self.max_amount:
            return money(0)
        if self.basis == CommissionRule.Basis.FIXED:
            return money(self.fixed_amount)
        return money(amount * self.rate / 100)


class CommissionTransaction(UUIDModel):
    class Status(models.TextChoices):
        ACCRUED = "ACCRUED", "Accrued"
        PAID = "PAID", "Paid"

    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="commissions")
    rule = models.ForeignKey(CommissionRule, on_delete=models.PROTECT, related_name="+")
    source = models.ForeignKey(
        AgentTransaction, on_delete=models.PROTECT, related_name="commissions"
    )
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACCRUED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "rule"], name="uniq_commission_per_rule"
            )
        ]
