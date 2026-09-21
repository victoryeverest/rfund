"""Savings domain models (spec §17–§21).

Products are versioned (§94): a plan always knows the exact product
configuration that created it.
"""

from django.db import models

from apps.core.models import UUIDModel


class SavingsProduct(models.Model):
    code = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    min_contribution = models.DecimalField(max_digits=19, decimal_places=2, default=100)
    max_contribution = models.DecimalField(max_digits=19, decimal_places=2, default=100000)
    allowed_frequencies = models.JSONField(default=list)  # ["DAILY",...]
    payout_policy = models.CharField(max_length=20, default="END_OF_TERM")
    allow_early_payout = models.BooleanField(default=False)
    status = models.CharField(max_length=10, default="ACTIVE")  # ACTIVE/RETIRED
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} v{self.version}"

    def current_config(self) -> dict:
        return {
            "code": self.code,
            "version": self.version,
            "min_contribution": str(self.min_contribution),
            "max_contribution": str(self.max_contribution),
            "allowed_frequencies": self.allowed_frequencies,
            "payout_policy": self.payout_policy,
            "allow_early_payout": self.allow_early_payout,
        }


class SavingsPlan(UUIDModel):
    class Frequency(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"
        BIYEARLY = "BIYEARLY", "Bi-yearly"
        YEARLY = "YEARLY", "Yearly"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        PAUSED = "PAUSED", "Paused"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="savings_plans"
    )
    product = models.ForeignKey(
        SavingsProduct, on_delete=models.PROTECT, related_name="plans"
    )
    product_config = models.JSONField(default=dict)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    frequency = models.CharField(max_length=12, choices=Frequency.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    payout_policy = models.CharField(max_length=20, default="END_OF_TERM")
    total_contributed = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0), name="savings_plan_positive_amount"
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.reference


class SavingsScheduleItem(UUIDModel):
    """Actual calendar dates — never fixed day multipliers (§18, §19)."""

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        DUE = "DUE", "Due"
        PAID = "PAID", "Paid"
        MISSED = "MISSED", "Missed"
        WAIVED = "WAIVED", "Waived"
        CANCELLED = "CANCELLED", "Cancelled"

    plan = models.ForeignKey(
        SavingsPlan, on_delete=models.CASCADE, related_name="schedule_items"
    )
    sequence = models.PositiveIntegerField()
    due_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UPCOMING)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        ordering = ["plan", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "sequence"], name="uniq_schedule_seq"),
            models.UniqueConstraint(fields=["plan", "due_date"], name="uniq_schedule_date"),
        ]
        indexes = [models.Index(fields=["status", "due_date"])]


class SavingsContribution(UUIDModel):
    plan = models.ForeignKey(
        SavingsPlan, on_delete=models.PROTECT, related_name="contributions"
    )
    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.PROTECT, related_name="savings_contribution"
    )
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        on_delete=models.PROTECT,
        related_name="savings_contributions",
    )
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    schedule_item = models.ForeignKey(
        SavingsScheduleItem, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at"]


class SavingsPayout(UUIDModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        VALIDATED = "VALIDATED", "Validated"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"

    reference = models.CharField(max_length=32, unique=True)
    plan = models.ForeignKey(SavingsPlan, on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="savings_payouts",
    )
    reason = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class SavingsGoal(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="savings_goals"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    target_amount = models.DecimalField(max_digits=19, decimal_places=2)
    current_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    contribution_frequency = models.CharField(max_length=12, default="MONTHLY")
    contribution_amount = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(target_amount__gt=0), name="goal_positive_target"
            ),
        ]
