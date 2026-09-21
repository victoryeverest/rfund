"""Concrete sequence model (separate file avoids circular import with services)."""

from django.db import models


class ReferenceSequence(models.Model):
    prefix = models.CharField(max_length=8)
    date_key = models.CharField(max_length=8)
    last_number = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        unique_together = [("prefix", "date_key")]
        db_table = "core_reference_sequence"

    def __str__(self) -> str:
        return f"{self.prefix}-{self.date_key}: {self.last_number}"
