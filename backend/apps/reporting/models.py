"""Reporting models (spec §117, §118)."""

from django.db import models

from apps.core.models import UUIDModel


class ReportRun(UUIDModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    report_type = models.CharField(max_length=40, db_index=True)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    storage_key = models.CharField(max_length=250, blank=True, default="")
    error = models.TextField(blank=True, default="")
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
