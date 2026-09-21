"""Notification models (spec §47, §48)."""

from django.db import models

from apps.core.models import UUIDModel


class NotificationTemplate(UUIDModel):
    event_code = models.CharField(max_length=40, db_index=True)
    channel = models.CharField(max_length=10)  # SMS/EMAIL/PUSH/WHATSAPP
    language = models.CharField(max_length=8, default="en")
    subject = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_code", "channel", "language"], name="uniq_notification_template"
            )
        ]

    def render_subject(self, payload: dict) -> str:
        return _render(self.subject, payload)

    def render_body(self, payload: dict) -> str:
        return _render(self.body, payload)


def _render(text: str, payload: dict) -> str:
    try:
        return text.format(**{k: v for k, v in payload.items()})
    except (KeyError, IndexError):
        return text


class OutboxEvent(UUIDModel):
    """Transactional outbox (§107): committed WITH the financial change."""

    event_code = models.CharField(max_length=40, db_index=True)
    payload = models.JSONField(default=dict)
    dispatched = models.BooleanField(default=False, db_index=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]


class NotificationDelivery(UUIDModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    event = models.ForeignKey(OutboxEvent, on_delete=models.PROTECT, related_name="deliveries")
    channel = models.CharField(max_length=10)
    recipient = models.CharField(max_length=200)
    subject = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField(blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=250, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
