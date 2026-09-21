"""Customer application services."""

from __future__ import annotations

import logging
from datetime import date

from django.db import transaction

from apps.accounts.models import normalize_phone
from apps.accounts.services import grant_role
from apps.audit.models import AuditAction, record_audit
from apps.core.errors import InvalidStateTransition, NotFound, ValidationFailed
from apps.core.middleware import get_request_id
from apps.core.references import next_reference
from apps.customers.models import Customer

logger = logging.getLogger("rfund.customers")


def get_customer(customer_id: str) -> Customer:
    try:
        return Customer.objects.get(pk=customer_id)
    except (Customer.DoesNotExist, ValueError):
        raise NotFound("Customer not found.")


@transaction.atomic
def create_customer_profile(
    *,
    user,
    first_name: str,
    last_name: str,
    middle_name: str = "",
    email: str = "",
    date_of_birth: date | None = None,
    gender: str = "",
    occupation: str = "",
    address: str = "",
    state: str = "",
    lga: str = "",
    community: str = "",
    preferred_language: str = "en",
    created_by=None,
) -> Customer:
    """Create the financial profile for an authenticated user."""
    if Customer.objects.filter(user=user).exists():
        raise ValidationFailed("This account already has a customer profile.")
    if not first_name.strip() or not last_name.strip():
        raise ValidationFailed("First and last name are required.")
    if date_of_birth and date_of_birth > date.today():
        raise ValidationFailed("Date of birth cannot be in the future.")
    customer = Customer(
        user=user,
        customer_reference=next_reference("CUS"),
        first_name=first_name.strip(),
        middle_name=middle_name.strip(),
        last_name=last_name.strip(),
        phone=user.phone,
        email=email or user.email,
        date_of_birth=date_of_birth,
        gender=gender,
        occupation=occupation,
        address=address,
        state=state,
        lga=lga,
        community=community,
        preferred_language=preferred_language,
    )
    customer.full_clean()
    customer.save()
    record_audit(
        action=AuditAction.CREATE,
        resource_type="customer",
        resource_id=str(customer.pk),
        actor=created_by or user,
        after={"reference": customer.customer_reference},
        request_id=get_request_id(),
    )
    return customer


def ensure_customer_profile(user) -> Customer:
    """Get or lazily create a minimal profile for a customer-role user."""
    profile = Customer.objects.filter(user=user).first()
    if profile:
        return profile
    return create_customer_profile(
        user=user,
        first_name=user.first_name or "Customer",
        last_name=user.last_name or user.phone[-4:],
    )


@transaction.atomic
def update_customer_profile(
    customer: Customer,
    *,
    updated_by=None,
    **fields,
) -> Customer:
    allowed = {
        "first_name", "middle_name", "last_name", "email", "date_of_birth",
        "gender", "occupation", "address", "state", "lga", "community",
        "preferred_language",
    }
    before = {}
    changed = False
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        old = getattr(customer, key)
        if old != value:
            before[key] = str(old)
            setattr(customer, key, value)
            changed = True
    if not changed:
        return customer
    customer.full_clean()
    customer.save()
    record_audit(
        action=AuditAction.UPDATE,
        resource_type="customer",
        resource_id=str(customer.pk),
        actor=updated_by,
        before=before,
        after={k: str(getattr(customer, k)) for k in before},
        request_id=get_request_id(),
    )
    return customer


@transaction.atomic
def set_customer_status(
    customer: Customer, new_status: str, *, actor=None, reason: str = ""
) -> Customer:
    valid = {Customer.Status.ACTIVE, Customer.Status.SUSPENDED, Customer.Status.DEACTIVATED}
    if new_status not in valid:
        raise ValidationFailed("Invalid customer status.")
    if customer.status == new_status:
        return customer
    before = customer.status
    customer.status = new_status
    customer.deactivated_at = (
        timezone_now() if new_status != Customer.Status.ACTIVE else None
    )
    customer.save(update_fields=["status", "deactivated_at", "updated_at"])
    record_audit(
        action=AuditAction.SUSPEND if new_status == "SUSPENDED" else (
            AuditAction.REINSTATE if new_status == "ACTIVE" else AuditAction.UPDATE
        ),
        resource_type="customer",
        resource_id=str(customer.pk),
        actor=actor,
        before={"status": before},
        after={"status": new_status},
        reason=reason,
        request_id=get_request_id(),
    )
    return customer


def timezone_now():
    from django.utils import timezone

    return timezone.now()
