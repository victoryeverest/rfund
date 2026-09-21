"""FarmerCash domain (spec §42, §43).

FarmerProfile extends Customer; farms/seasons/inputs model the production
cycle; financing links to ordinary Loan rows (one money system — §191).
"""

from django.db import models

from apps.core.models import UUIDModel


class FarmerProfile(UUIDModel):
    customer = models.OneToOneField(
        "customers.Customer", on_delete=models.PROTECT, related_name="farmer_profile"
    )
    years_of_experience = models.PositiveIntegerField(default=0)
    primary_crops = models.JSONField(default=list)
    farming_type = models.CharField(max_length=20, default="SMALLHOLDER")
    cooperative = models.ForeignKey(
        "cooperatives.Cooperative",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="farmers",
    )
    verified = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Farmer {self.customer_id}"


class Farm(UUIDModel):
    farmer = models.ForeignKey(
        FarmerProfile, on_delete=models.PROTECT, related_name="farms"
    )
    name = models.CharField(max_length=120, blank=True, default="")
    state = models.CharField(max_length=60)
    lga = models.CharField(max_length=80, blank=True, default="")
    community = models.CharField(max_length=120, blank=True, default="")
    size_hectares = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # GPS protected: never exposed without permission (§44)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    ownership = models.CharField(max_length=20, default="OWNED")  # OWNED/LEASED/COMMUNAL

    class Meta:
        ordering = ["-created_at"]

    @property
    def location_display(self) -> str:
        return f"{self.community}, {self.lga}, {self.state}".strip(", ")


class FarmSeason(UUIDModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        ACTIVE = "ACTIVE", "Active"
        HARVESTED = "HARVESTED", "Harvested"
        CANCELLED = "CANCELLED", "Cancelled"

    farm = models.ForeignKey(Farm, on_delete=models.PROTECT, related_name="seasons")
    crop = models.ForeignKey("agriculture.Crop", on_delete=models.PROTECT, related_name="+")
    season_name = models.CharField(max_length=40)  # e.g. "2026 Wet Season"
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    expected_yield_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_harvest_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-starts_on"]


class FieldVerification(UUIDModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"

    farm = models.ForeignKey(Farm, on_delete=models.PROTECT, related_name="verifications")
    verifier = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    application = models.ForeignKey(
        "loans.LoanApplication",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="field_verifications",
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    photos = models.JSONField(default=list)  # private storage keys
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
