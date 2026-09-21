"""Base models (spec §8): UUID primary keys + separate public references.

Never expose sequential database IDs as the public identifier.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

from django.db import models


def utcnow() -> datetime:
    """Timezone-aware UTC now (spec §95: UTC internally, never naive)."""
    return datetime.now(tz=dt_timezone.utc)


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def public_id(self) -> str:
        """Stable public identifier for API exposure (UUID, not sequential)."""
        return str(self.id)


class AuditFieldsModel(models.Model):
    """Adds actor tracking for records that require attribution."""

    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True

# Import for Django model discovery (sequence counter used by references.py)
from apps.core.sequence_models import ReferenceSequence  # noqa: E402,F401
