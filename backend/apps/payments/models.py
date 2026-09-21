"""Payments domain models (spec §24, §26, §28).

The application never talks to Paystack directly — only through the
PaymentProvider abstraction in integrations/payments/.
"""

from django.db import models

from apps.core.models import UUIDModel


class Payment(UUIDModel):
    """A customer-facing payment (inbound money)."""

    class Purpose(models.TextChoices):
        SAVINGS_CONTRIBUTION = "SAVINGS_CONTRIBUTION", "Savings contribution"
        GOAL_FUNDING = "GOAL_FUNDING", "Savings goal funding"
        LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
        ACCOUNT_FUNDING = "ACCOUNT_FUNDING", "Account funding"

    class Status(models.TextChoices):
        INITIALIZED = "INITIALIZED", "Initialized"
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        REVERSED = "REVERSED", "Reversed"
        REFUNDED = "REFUNDED", "Refunded"
        SETTLED = "SETTLED", "Settled"

    class Method(models.TextChoices):
        CARD = "CARD", "Card"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        USSD = "USSD", "USSD"
        AGENT_CASH = "AGENT_CASH", "Agent cash"
        WALLET = "WALLET", "Wallet"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="payments"
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices, db_index=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INITIALIZED)
    method = models.CharField(max_length=16, choices=Method.choices, blank=True, default="")
    provider = models.CharField(max_length=20, blank=True, default="")
    provider_reference = models.CharField(max_length=120, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    # What this payment settles once successful (JSON: plan id, goal id, loan id…)
    target = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=250, blank=True, default="")
    initiated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    ledger_transaction = models.ForeignKey(
        "ledger.LedgerTransaction",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    device_id = models.CharField(max_length=120, blank=True, default="")
    client_reference = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0), name="payment_positive_amount"
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_payment_idempotency_key",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["provider", "provider_reference"]),
        ]

    def __str__(self) -> str:
        return self.reference


class PaymentAttempt(UUIDModel):
    """Each provider call made to initialize/charge a payment (§24)."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="attempts")
    provider = models.CharField(max_length=20)
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=12)  # INITIALIZED/PENDING/SUCCESS/FAILED
    authorization_url = models.TextField(blank=True, default="")
    raw_response = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        ordering = ["created_at"]


class PaymentWebhookEvent(UUIDModel):
    """Raw provider webhook storage — persisted before processing (§25, §109)."""

    provider = models.CharField(max_length=20, db_index=True)
    event_id = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=60, blank=True, default="")
    payload = models.JSONField()
    signature_valid = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processing_status = models.CharField(
        max_length=16, default="RECEIVED"
    )  # RECEIVED/PROCESSING/PROCESSED/FAILED/DEAD
    processing_error = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="webhook_events"
    )

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"], name="uniq_webhook_event"
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"


class PaymentProviderEvent(UUIDModel):
    """Normalized mirror of provider-side transactions for reconciliation (§27)."""

    provider = models.CharField(max_length=20, db_index=True)
    provider_reference = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=60, blank=True, default="")
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=20)
    occurred_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(null=True, blank=True)
    reconciled = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                condition=~models.Q(provider_reference=""),
                name="uniq_provider_event_reference",
            )
        ]


class VirtualAccount(UUIDModel):
    """Dedicated virtual account architecture (§26). Provider-agnostic."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FROZEN = "FROZEN", "Frozen"
        CLOSED = "CLOSED", "Closed"

    provider = models.CharField(max_length=20, db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True, default="", db_index=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="virtual_accounts"
    )
    account_number = models.CharField(max_length=40, blank=True, default="")
    bank_name = models.CharField(max_length=80, blank=True, default="")
    bank_code = models.CharField(max_length=20, blank=True, default="")
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "account_number"],
                condition=~models.Q(account_number=""),
                name="uniq_virtual_account_number",
            )
        ]
