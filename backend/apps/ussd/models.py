"""USSD preparation (spec §99, §148, §188).

Architecture ONLY — no fake functionality. The session model lets a
future USSD gateway track menu state; handlers will call the SAME
application services as web/mobile (never direct database writes).
"""

from django.db import models

from apps.core.models import UUIDModel


class USSDSession(UUIDModel):
    """A USSD dialogue between a subscriber and RFUND.

    V2 will wire a real provider (gateway) to apps.* services.
    """

    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    msisdn = models.CharField(max_length=16, db_index=True)
    provider = models.CharField(max_length=20, blank=True, default="")
    menu_path = models.JSONField(default=list)
    state = models.CharField(max_length=20, default="STARTED")
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
