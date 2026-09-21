"""Customer financial-party profile (spec §9).

Separate from the auth User (spec §10). Never deleted once it has
financial history — lifecycle status only (spec §120).
"""

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel


class Customer(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DEACTIVATED = "DEACTIVATED", "Deactivated"

    class Gender(models.TextChoices):
        FEMALE = "FEMALE", "Female"
        MALE = "MALE", "Male"
        OTHER = "OTHER", "Other"
        UNDISCLOSED = "UNDISCLOSED", "Prefer not to say"

    class Language(models.TextChoices):
        EN = "en", "English"
        HA = "ha", "Hausa"
        YO = "yo", "Yoruba"
        IG = "ig", "Igbo"
        PCM = "pcm", "Nigerian Pidgin"

    user = models.OneToOneField(
        "accounts.User", on_delete=models.PROTECT, related_name="customer_profile"
    )
    customer_reference = models.CharField(max_length=32, unique=True, db_index=True)
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=12, choices=Gender.choices, blank=True, default="")
    occupation = models.CharField(max_length=120, blank=True, default="")
    address = models.CharField(max_length=200, blank=True, default="")
    state = models.CharField(max_length=60, blank=True, default="")
    lga = models.CharField(max_length=80, blank=True, default="")
    community = models.CharField(max_length=120, blank=True, default="")
    preferred_language = models.CharField(
        max_length=8, choices=Language.choices, default=Language.EN
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    kyc_tier = models.CharField(max_length=10, default="BASIC")
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["status"]),
            models.Index(fields=["state", "lga"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.customer_reference})"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()
