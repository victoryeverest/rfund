"""Loan domain models (spec §36–§41).

State machine (§37):
  DRAFT → SUBMITTED → UNDER_REVIEW → (VERIFICATION_REQUIRED)?
        → APPROVED → OFFERED → ACCEPTED → DISBURSED → ACTIVE
        → COMPLETED / DELINQUENT / DEFAULTED / RESTRUCTURED
  Any pre-money state may → REJECTED / CANCELLED.
"""

from django.db import models

from apps.core.models import UUIDModel


class LoanProduct(models.Model):
    code = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    min_amount = models.DecimalField(max_digits=19, decimal_places=2)
    max_amount = models.DecimalField(max_digits=19, decimal_places=2)
    term_values = models.JSONField(default=list)  # e.g. [3, 6, 12] months
    repayment_frequency = models.CharField(max_length=12, default="MONTHLY")
    interest_method = models.CharField(max_length=24, default="FLAT")  # FLAT / DECLINING_BALANCE
    interest_rate = models.DecimalField(max_digits=6, decimal_places=4)  # annual %, e.g. 24.0000
    fees = models.JSONField(default=dict)  # {"origination": {"type":"percent","value":1.5}}
    penalty_policy = models.JSONField(default=dict)  # {"late":{"type":"fixed","value":500,"grace_days":3}}
    allocation_order = models.JSONField(default=list)  # ["PENALTY","FEES","INTEREST","PRINCIPAL"]
    eligibility_rules = models.JSONField(default=dict)
    required_documents = models.JSONField(default=list)
    status = models.CharField(max_length=10, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def current_config(self) -> dict:
        return {
            "code": self.code,
            "version": self.version,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "term_values": self.term_values,
            "repayment_frequency": self.repayment_frequency,
            "interest_method": self.interest_method,
            "interest_rate": str(self.interest_rate),
            "fees": self.fees,
            "penalty_policy": self.penalty_policy,
            "allocation_order": self.allocation_order,
        }


class LoanApplication(UUIDModel):
    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED", "Verification required"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        OFFERED = "OFFERED", "Offered"
        ACCEPTED = "ACCEPTED", "Accepted"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="loan_applications"
    )
    product = models.ForeignKey(
        LoanProduct, on_delete=models.PROTECT, related_name="applications"
    )
    product_config = models.JSONField(default=dict)
    amount_requested = models.DecimalField(max_digits=19, decimal_places=2)
    term_months = models.PositiveIntegerField()
    purpose = models.TextField(blank=True, default="")
    state = models.CharField(max_length=22, choices=State.choices, default=State.DRAFT, db_index=True)
    # Business / farm information captured at application time
    business_info = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self) -> str:
        return self.reference


class LoanOffer(UUIDModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    application = models.OneToOneField(
        LoanApplication, on_delete=models.PROTECT, related_name="offer"
    )
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=4)
    term_months = models.PositiveIntegerField()
    total_repayable = models.DecimalField(max_digits=19, decimal_places=2)
    first_payment_date = models.DateField()
    expires_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Loan(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DELINQUENT = "DELINQUENT", "Delinquent"
        DEFAULTED = "DEFAULTED", "Defaulted"
        RESTRUCTURED = "RESTRUCTURED", "Restructured"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    application = models.OneToOneField(
        LoanApplication, on_delete=models.PROTECT, related_name="loan"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="loans"
    )
    product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT, related_name="loans")
    product_config = models.JSONField(default=dict)
    principal = models.DecimalField(max_digits=19, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=4)
    interest_method = models.CharField(max_length=24, default="FLAT")
    term_months = models.PositiveIntegerField()
    total_interest = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    total_fees = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    outstanding_principal = models.DecimalField(max_digits=19, decimal_places=2)
    outstanding_interest = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    outstanding_fees = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.ACTIVE)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="loans",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.reference

    @property
    def total_outstanding(self):
        return self.outstanding_principal + self.outstanding_interest + self.outstanding_fees


class RepaymentScheduleItem(UUIDModel):
    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        DUE = "DUE", "Due"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
        PAID = "PAID", "Paid"
        LATE = "LATE", "Late"
        WAIVED = "WAIVED", "Waived"
        RESTRUCTURED = "RESTRUCTURED", "Restructured"

    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, related_name="repayment_schedule"
    )
    sequence = models.PositiveIntegerField()
    due_date = models.DateField(db_index=True)
    principal_due = models.DecimalField(max_digits=19, decimal_places=2)
    interest_due = models.DecimalField(max_digits=19, decimal_places=2)
    fees_due = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    penalty_due = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPCOMING)

    class Meta:
        ordering = ["loan", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "sequence"], name="uniq_repayment_seq")
        ]

    @property
    def total_due(self):
        return self.principal_due + self.interest_due + self.fees_due + self.penalty_due

    @property
    def outstanding(self):
        return self.total_due - self.amount_paid


class Repayment(UUIDModel):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.PROTECT, related_name="loan_repayment"
    )
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    allocation = models.JSONField(default=dict)  # {"penalty":x,"fees":y,"interest":z,"principal":w}
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        on_delete=models.PROTECT,
        related_name="loan_repayments",
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at"]


class Penalty(UUIDModel):
    class Status(models.TextChoices):
        OUTSTANDING = "OUTSTANDING", "Outstanding"
        WAIVED = "WAIVED", "Waived"
        PAID = "PAID", "Paid"

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="penalties")
    schedule_item = models.ForeignKey(
        RepaymentScheduleItem, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OUTSTANDING)
    waived_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
