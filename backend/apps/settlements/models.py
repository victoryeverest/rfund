"""Reconciliation subsystem (spec §27)."""

from django.db import models

from apps.core.models import UUIDModel


class ReconciliationRun(UUIDModel):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    provider = models.CharField(max_length=20, db_index=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    matched_count = models.PositiveIntegerField(default=0)
    exception_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]


class ReconciliationItem(UUIDModel):
    class Status(models.TextChoices):
        MATCHED = "MATCHED", "Matched"
        MISSING_PROVIDER = "MISSING_PROVIDER", "Missing on provider"
        MISSING_INTERNAL = "MISSING_INTERNAL", "Missing internally"
        AMOUNT_MISMATCH = "AMOUNT_MISMATCH", "Amount mismatch"
        DUPLICATE = "DUPLICATE", "Duplicate"
        PENDING = "PENDING", "Pending"
        MANUAL_REVIEW = "MANUAL_REVIEW", "Manual review"

    run = models.ForeignKey(ReconciliationRun, on_delete=models.PROTECT, related_name="items")
    internal_reference = models.CharField(max_length=40, blank=True, default="", db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True, default="", db_index=True)
    internal_amount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    provider_amount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "provider_reference"],
                condition=~models.Q(provider_reference=""),
                name="uniq_recon_item_provider_ref",
            )
        ]


class ReconciliationException(UUIDModel):
    item = models.OneToOneField(ReconciliationItem, on_delete=models.PROTECT, related_name="exception")
    reason = models.TextField(blank=True, default="")
    resolution = models.TextField(blank=True, default="")
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
