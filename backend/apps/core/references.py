"""Human-readable reference numbers (spec §8, §49).

Format: RF-<PREFIX>-<YYYYMMDD>-<NNNNNN>
Example: RF-SAV-20260921-000001

Sequences are per (prefix, date) and generated with row-level locking so
concurrent requests can never receive the same number.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.errors import ValidationFailed


def _sequence_model():
    from apps.core.sequence_models import ReferenceSequence as RS

    return RS


@transaction.atomic
def next_reference(prefix: str) -> str:
    """Generate the next human-readable reference for `prefix`.

    MUST be called inside the same transaction as the record it names,
    so a rollback also rolls back the sequence.
    """
    if not prefix or not prefix.replace("-", "").isalnum():
        raise ValidationFailed("Reference prefix must be alphanumeric.")
    prefix = prefix.upper()
    today = timezone.now().strftime("%Y%m%d")
    RS = _sequence_model()
    seq, _created = (
        RS.objects.select_for_update()
        .get_or_create(prefix=prefix, date_key=today, defaults={"last_number": 0})
    )
    number = F("last_number") + 1
    RS.objects.filter(pk=seq.pk).update(last_number=number)
    seq.refresh_from_db()
    return f"RF-{prefix}-{today}-{seq.last_number:06d}"


def parse_reference(reference: str) -> tuple[str, str, int] | None:
    """Validate the shape RF-PREFIX-YYYYMMDD-NNNNNN. Returns parts or None."""
    import re

    if not reference:
        return None
    match = re.fullmatch(r"RF-([A-Z]+)-(\d{8})-(\d{6})", reference.strip().upper())
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))
