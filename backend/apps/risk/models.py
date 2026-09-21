"""Risk engine models (spec §45). Deterministic, explainable."""

from django.db import models

from apps.core.models import UUIDModel


class RiskRule(UUIDModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    signal = models.CharField(max_length=40)
    weight = models.PositiveIntegerField(default=10)
    parameters = models.JSONField(default=dict)
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return self.code


class RiskAssessment(UUIDModel):
    application = models.OneToOneField(
        "loans.LoanApplication", on_delete=models.PROTECT, related_name="assessment"
    )
    score = models.DecimalField(max_digits=6, decimal_places=2)
    decision = models.CharField(max_length=10)  # APPROVE / REVIEW / REJECT
    model_version = models.CharField(max_length=20, default="rules-v1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RiskFactor(UUIDModel):
    assessment = models.ForeignKey(
        RiskAssessment, on_delete=models.PROTECT, related_name="factors"
    )
    rule_code = models.CharField(max_length=40)
    input_value = models.CharField(max_length=250)
    score = models.PositiveIntegerField()
    weight = models.CharField(max_length=10)
    explanation = models.CharField(max_length=250)
