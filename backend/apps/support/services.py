"""Support services (spec §51)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.errors import InvalidStateTransition, NotFound, ValidationFailed
from apps.core.references import next_reference
from apps.support.models import SupportMessage, SupportTicket


@transaction.atomic
def create_ticket(*, customer, category: str, subject: str, body: str, created_by=None):
    if not subject.strip():
        raise ValidationFailed("Please describe the problem in a few words.")
    if category not in SupportTicket.Category.values:
        raise ValidationFailed("Invalid support category.")
    ticket = SupportTicket.objects.create(
        reference=next_reference("SUP"),
        customer=customer,
        category=category,
        subject=subject.strip()[:200],
    )
    SupportMessage.objects.create(
        ticket=ticket, sender=created_by or customer.user, body=body[:5000]
    )
    return ticket


def get_ticket(ticket_id: str, *, customer=None) -> SupportTicket:
    try:
        ticket = SupportTicket.objects.select_related("customer").get(pk=ticket_id)
    except (SupportTicket.DoesNotExist, ValueError):
        raise NotFound("Support ticket not found.")
    if customer is not None and ticket.customer_id != customer.pk:
        raise NotFound("Support ticket not found.")  # object-level authz
    return ticket


@transaction.atomic
def reply_ticket(ticket: SupportTicket, *, sender, body: str, internal: bool = False):
    if ticket.status in (SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED):
        raise InvalidStateTransition("This ticket is closed.")
    if internal and not sender.has_perm_code("support.write"):
        raise ValidationFailed("Only staff can add internal notes.")
    message = SupportMessage.objects.create(
        ticket=ticket, sender=sender, body=body[:5000], internal=internal
    )
    if not internal:
        if sender.pk == ticket.customer.user_id:
            ticket.status = SupportTicket.Status.WAITING_CUSTOMER if ticket.assignee else SupportTicket.Status.OPEN
        else:
            ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])
    return message


@transaction.atomic
def set_ticket_status(ticket: SupportTicket, status: str, *, actor):
    if status not in SupportTicket.Status.values:
        raise ValidationFailed("Invalid ticket status.")
    ticket.status = status
    ticket.save(update_fields=["status", "updated_at"])
    return ticket
