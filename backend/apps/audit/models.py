"""Append-only audit trail (spec §50, §165).

Financial audit events are immutable: updates and deletes are rejected at
the model layer and there is no admin/write surface other than record().

Model methods deliberately raise on save() of an existing row and on
delete() — corrections are new compensating events, never edits.
"""

from __future__ import annotations

import logging

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDModel

logger = logging.getLogger("rfund.audit")


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    LOGIN = "LOGIN", "Login"
    LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
    LOGOUT = "LOGOUT", "Logout"
    APPROVE = "APPROVE", "Approve"
    REJECT = "REJECT", "Reject"
    REVERSE = "REVERSE", "Reverse"
    REFUND = "REFUND", "Refund"
    DISBURSE = "DISBURSE", "Disburse"
    SETTLE = "SETTLE", "Settle"
    SUSPEND = "SUSPEND", "Suspend"
    REINSTATE = "REINSTATE", "Reinstate"
    VERIFY = "VERIFY", "Verify"
    FLAG = "FLAG", "Flag"
    CLEAR = "CLEAR", "Clear"
    EXPORT = "EXPORT", "Export"
    CONFIG_CHANGE = "CONFIG_CHANGE", "Configuration change"
    REVIEW = "REVIEW", "Review"
    ASSIGN = "ASSIGN", "Assign"


class AuditEvent(UUIDModel):
    """who / what / when / resource / before / after / IP / device / reason."""

    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor_label = models.CharField(max_length=120, blank=True, default="")
    action = models.CharField(max_length=20, choices=AuditAction.choices, db_index=True)
    resource_type = models.CharField(max_length=60, db_index=True)
    resource_id = models.CharField(max_length=64, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_id = models.CharField(max_length=120, blank=True, default="")
    request_id = models.CharField(max_length=40, blank=True, default="")
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["actor", "-occurred_at"]),
        ]

    # -- Immutability -------------------------------------------------------
    def save(self, *args, **kwargs):  # noqa: D102
        if not self._state.adding and not kwargs.pop("allow_immutable_create", False):
            raise RuntimeError(
                "AuditEvent rows are append-only. Create a new event instead."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: D102
        raise RuntimeError("AuditEvent rows can never be deleted.")

    def __str__(self) -> str:
        return f"{self.action} {self.resource_type}:{self.resource_id}"


def record_audit(
    *,
    action: AuditAction | str,
    resource_type: str,
    resource_id: str,
    actor=None,
    actor_label: str = "",
    before: dict | None = None,
    after: dict | None = None,
    reason: str = "",
    ip_address=None,
    device_id: str = "",
    request_id: str = "",
    commit: bool = True,
) -> AuditEvent:
    """Create an audit event. Call inside the audited transaction when possible."""
    from apps.audit.models import AuditAction as AA

    if isinstance(action, str):
        action = AA(action)
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        actor=actor,
        actor_label=actor_label or (str(actor) if actor else "system"),
        before=before,
        after=after,
        reason=reason,
        ip_address=ip_address,
        device_id=device_id,
        request_id=request_id,
    )
    if commit:
        event.save()
    logger.info(
        "audit_event",
        extra={
            "event": "audit_event",
            "action": str(action),
            "resource": f"{resource_type}:{resource_id}",
            "actor": event.actor_label,
        },
    )
    return event
