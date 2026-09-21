"""Agricultural reference data + season activities (spec §42)."""

from django.db import models

from apps.core.models import UUIDModel


class Crop(models.Model):
    code = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=30, default="FOOD")  # FOOD/CASH/LIVESTOCK_FEED

    class Meta:
        ordering = ["name"]


class InputSupplier(UUIDModel):
    name = models.CharField(max_length=120)
    state = models.CharField(max_length=60, blank=True, default="")
    lga = models.CharField(max_length=80, blank=True, default="")
    input_types = models.JSONField(default=list)  # ["SEED","FERTILIZER",...]
    phone = models.CharField(max_length=16, blank=True, default="")
    status = models.CharField(max_length=10, default="ACTIVE")

    class Meta:
        ordering = ["name"]


class InputRequirement(UUIDModel):
    class InputType(models.TextChoices):
        SEED = "SEED", "Seed"
        FERTILIZER = "FERTILIZER", "Fertilizer"
        AGROCHEMICAL = "AGROCHEMICAL", "Agrochemical"
        LABOUR = "LABOUR", "Labour"
        TRANSPORT = "TRANSPORT", "Transport"
        STORAGE = "STORAGE", "Storage"
        IRRIGATION = "IRRIGATION", "Irrigation"
        OTHER = "OTHER", "Other"

    season = models.ForeignKey(
        "farmers.FarmSeason", on_delete=models.PROTECT, related_name="input_requirements"
    )
    input_type = models.CharField(max_length=16, choices=InputType.choices)
    description = models.CharField(max_length=200, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, default="unit")
    unit_cost = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    supplier = models.ForeignKey(
        InputSupplier, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost


class FarmActivity(UUIDModel):
    season = models.ForeignKey(
        "farmers.FarmSeason", on_delete=models.PROTECT, related_name="activities"
    )
    activity = models.CharField(max_length=40)  # LAND_PREP/PLANTING/WEEDING/...
    performed_on = models.DateField()
    notes = models.TextField(blank=True, default="")
    cost = models.DecimalField(max_digits=19, decimal_places=2, default=0)

    class Meta:
        ordering = ["performed_on"]


class Harvest(UUIDModel):
    season = models.OneToOneField(
        "farmers.FarmSeason", on_delete=models.PROTECT, related_name="harvest"
    )
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=2)
    harvested_on = models.DateField()
    buyer_name = models.CharField(max_length=120, blank=True, default="")
    price_per_kg = models.DecimalField(max_digits=19, decimal_places=2, default=0)
