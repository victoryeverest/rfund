"""Organizations: cooperatives, NGOs, partners, funders (spec §35)."""

from django.db import models

from apps.core.models import UUIDModel


class Organization(UUIDModel):
    class Type(models.TextChoices):
        COOPERATIVE = "COOPERATIVE", "Cooperative"
        NGO = "NGO", "NGO"
        PARTNER = "PARTNER", "Partner"
        FUNDER = "FUNDER", "Institutional funder"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DEACTIVATED = "DEACTIVATED", "Deactivated"

    name = models.CharField(max_length=160)
    type = models.CharField(max_length=14, choices=Type.choices, db_index=True)
    registration_number = models.CharField(max_length=60, blank=True, default="")
    state = models.CharField(max_length=60, blank=True, default="")
    lga = models.CharField(max_length=80, blank=True, default="")
    community = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=16, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
