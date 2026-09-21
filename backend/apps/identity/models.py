"""Identity & KYC (spec §12, §159).

- Configurable identity types (NIN, BVN, PASSPORT, ...)
- IdentityVerificationProvider abstraction — vendors never hard-coded
- KYC levels BASIC/STANDARD/ENHANCED with configurable limits
- Sensitive documents live in private storage, never public URLs
"""

from django.db import models

from apps.core.models import UUIDModel


class KYCProfile(UUIDModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        PENDING = "PENDING", "Pending"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    class Level(models.TextChoices):
        BASIC = "BASIC", "Basic"
        STANDARD = "STANDARD", "Standard"
        ENHANCED = "ENHANCED", "Enhanced"

    customer = models.OneToOneField(
        "customers.Customer", on_delete=models.PROTECT, related_name="kyc_profile"
    )
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.NOT_STARTED)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.BASIC)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"KYC {self.customer_id} {self.status}"


class IdentityDocument(UUIDModel):
    class DocType(models.TextChoices):
        NIN = "NIN", "National Identity Number"
        BVN = "BVN", "Bank Verification Number"
        PASSPORT = "PASSPORT", "International passport"
        DRIVERS_LICENSE = "DRIVERS_LICENSE", "Driver's licence"
        VOTERS_CARD = "VOTERS_CARD", "Voter's card"
        OTHER = "OTHER", "Other"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="identity_documents"
    )
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    number_encrypted = models.TextField()  # application-level encryption
    storage_key = models.CharField(max_length=200, blank=True, default="")
    country = models.CharField(max_length=2, default="NG")
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "doc_type"], name="uniq_customer_doc_type"
            )
        ]

    def set_number(self, number: str) -> None:
        from apps.identity.crypto import encrypt_value

        self.number_encrypted = encrypt_value(number)

    def get_number(self) -> str:
        from apps.identity.crypto import decrypt_value

        return decrypt_value(self.number_encrypted)

    def masked_number(self) -> str:
        """Display form: last 3 chars only (spec §63: minimize sensitive data)."""
        number = self.get_number()
        if len(number) <= 3:
            return "*" * len(number)
        return "*" * (len(number) - 3) + number[-3:]


class KYCVerification(UUIDModel):
    """Result of an external verification attempt through a provider."""

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="kyc_verifications"
    )
    document = models.ForeignKey(
        IdentityDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    provider = models.CharField(max_length=40)
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20)  # provider-agnostic: PENDING/SUCCESS/FAILED
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                condition=~models.Q(provider_reference=""),
                name="uniq_kyc_provider_reference",
            )
        ]


class KYCReview(UUIDModel):
    reviewer = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="kyc_reviews"
    )
    profile = models.ForeignKey(
        KYCProfile, on_delete=models.PROTECT, related_name="reviews"
    )
    decision = models.CharField(max_length=10)  # APPROVED / REJECTED / INFO_REQUESTED
    reason = models.TextField(blank=True, default="")
    before_status = models.CharField(max_length=14)
    after_status = models.CharField(max_length=14)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]
