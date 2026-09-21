"""Fraud detection models (spec §46).

People are never auto-labelled fraudulent — alerts go to investigation
workflow with FLAGGED/UNDER_REVIEW/CLEARED/CONFIRMED states.
"""

from django.db import models

from apps.core.models import UUIDModel


class FraudRule(UUIDModel):
    code = models.CharField(max_length=40, unique=True)
    detector = models.CharField(max_length=40)
    parameters = models.JSONField(default=dict)
    description = models.CharField(max_length=250, blank=True, default="")
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code


class FraudAlert(UUIDModel):
    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        FLAGGED = "FLAGGED", "Flagged"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        CLEARED = "CLEARED", "Cleared"
        CONFIRMED = "CONFIRMED", "Confirmed"

    rule = models.ForeignKey(FraudRule, on_delete=models.PROTECT, related_name="alerts")
    resource_type = models.CharField(max_length=40)
    resource_id = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=8, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.FLAGGED, db_index=True)
    details = models.JSONField(default=dict)
    assigned_to = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="fraud_alerts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class FraudCase(UUIDModel):
    alert = models.OneToOneField(FraudAlert, on_delete=models.PROTECT, related_name="case")
    investigation_notes = models.TextField(blank=True, default="")
    outcome = models.CharField(max_length=20, blank=True, default="")
    resolved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
