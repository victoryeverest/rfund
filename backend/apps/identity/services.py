"""KYC application services + verification provider abstraction (spec §12)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction, record_audit
from apps.core.errors import InvalidStateTransition, PermissionDenied, ValidationFailed
from apps.core.middleware import get_request_id
from apps.identity.models import (
    IdentityDocument,
    KYCProfile,
    KYCReview,
    KYCVerification,
)
from apps.notifications.services import emit_event

logger = logging.getLogger("rfund.identity")


# ---------------------------------------------------------------------------
# IdentityVerificationProvider abstraction (spec §12) — vendors swappable
# ---------------------------------------------------------------------------
class IdentityVerificationProvider:
    """Interface. Adapters live in integrations/identity/."""

    code = "abstract"

    def verify(self, *, doc_type: str, number: str, customer_data: dict) -> dict:
        raise NotImplementedError

    def name(self) -> str:
        return self.code


def get_identity_provider() -> IdentityVerificationProvider | None:
    from django.conf import settings

    provider_name = getattr(settings, "IDENTITY_PROVIDER", "manual")
    if provider_name == "manual":
        return None
    from integrations.identity.providers import get_provider

    return get_provider(provider_name)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
def get_or_create_profile(customer) -> KYCProfile:
    profile, _ = KYCProfile.objects.get_or_create(customer=customer)
    return profile


@transaction.atomic
def submit_kyc(
    customer,
    *,
    doc_type: str,
    id_number: str,
    storage_key: str = "",
    issued_at=None,
    expires_at=None,
    submitted_by=None,
) -> KYCProfile:
    """Customer submits an identity document for verification (spec §12)."""
    if doc_type not in IdentityDocument.DocType.values:
        raise ValidationFailed("Unsupported identity document type.")
    if not id_number or len(id_number.strip()) < 6:
        raise ValidationFailed("The identity number is not valid.")
    profile = get_or_create_profile(customer)
    if profile.status in (KYCProfile.Status.VERIFIED, KYCProfile.Status.UNDER_REVIEW):
        raise InvalidStateTransition(
            "Your identity verification is already in progress or complete."
        )

    document = IdentityDocument.objects.filter(customer=customer, doc_type=doc_type).first()
    if document is None:
        document = IdentityDocument(customer=customer, doc_type=doc_type)
    document.set_number(id_number.strip())
    document.storage_key = storage_key
    document.issued_at = issued_at
    document.expires_at = expires_at
    document.verified = False
    document.save()

    provider = get_identity_provider()
    if provider is not None:
        verification = KYCVerification.objects.create(
            customer=customer,
            document=document,
            provider=provider.code,
            status="PENDING",
        )
        try:
            result = provider.verify(
                doc_type=doc_type, number=id_number.strip(), customer_data={"phone": customer.phone}
            )
            verification.status = result.get("status", "FAILED")
            verification.provider_reference = result.get("reference", "")
            verification.result = result
            verification.save()
            if verification.status == "SUCCESS":
                document.verified = True
                document.save(update_fields=["verified"])
        except Exception as exc:  # provider failure → manual review, never crash
            verification.status = "FAILED"
            verification.result = {"error": str(exc)[:200]}
            verification.save()
            logger.warning("identity_provider_failed", extra={"provider": provider.code})

    before = profile.status
    profile.status = KYCProfile.Status.PENDING
    profile.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.CREATE,
        resource_type="kyc_profile",
        resource_id=str(profile.pk),
        actor=submitted_by or customer.user,
        before={"status": before},
        after={"status": profile.status, "doc_type": doc_type},
        request_id=get_request_id(),
    )
    emit_event("KYC_SUBMITTED", {"customer_id": str(customer.pk)})
    return profile


@transaction.atomic
def review_kyc(
    profile: KYCProfile,
    *,
    reviewer,
    decision: str,
    reason: str = "",
    new_level: str | None = None,
) -> KYCProfile:
    """KYC officer decision (permission checked at the resolver)."""
    if profile.status not in (KYCProfile.Status.PENDING, KYCProfile.Status.UNDER_REVIEW):
        raise InvalidStateTransition("This verification is not awaiting review.")
    if decision not in {"APPROVED", "REJECTED", "INFO_REQUESTED"}:
        raise ValidationFailed("Invalid review decision.")
    if decision == "APPROVED" and not reason.strip():
        raise ValidationFailed("An approval reason is required for the audit trail.")

    before = profile.status
    if decision == "APPROVED":
        profile.status = KYCProfile.Status.VERIFIED
        profile.verified_at = timezone.now()
        profile.failure_reason = ""
        if new_level in KYCProfile.Level.values:
            profile.level = new_level
            profile.customer.kyc_tier = new_level
            profile.customer.save(update_fields=["kyc_tier", "updated_at"])
    elif decision == "REJECTED":
        profile.status = KYCProfile.Status.REJECTED
        profile.failure_reason = reason
    else:  # INFO_REQUESTED
        profile.status = KYCProfile.Status.UNDER_REVIEW

    profile.save()
    KYCReview.objects.create(
        reviewer=reviewer,
        profile=profile,
        decision=decision,
        reason=reason,
        before_status=before,
        after_status=profile.status,
    )
    record_audit(
        action=AuditAction.REVIEW,
        resource_type="kyc_profile",
        resource_id=str(profile.pk),
        actor=reviewer,
        before={"status": before},
        after={"status": profile.status, "level": profile.level},
        reason=reason,
        request_id=get_request_id(),
    )
    if profile.status == KYCProfile.Status.VERIFIED:
        emit_event("KYC_VERIFIED", {"customer_id": str(profile.customer_id)})
    return profile


def require_verified_kyc(customer, *, minimum_level: str = KYCProfile.Level.BASIC) -> None:
    """Gate financial actions on KYC status where the product requires it."""
    profile = KYCProfile.objects.filter(customer=customer).first()
    if profile is None or profile.status != KYCProfile.Status.VERIFIED:
        from apps.core.errors import KYCRequired

        raise KYCRequired()
    order = [KYCProfile.Level.BASIC, KYCProfile.Level.STANDARD, KYCProfile.Level.ENHANCED]
    if order.index(profile.level) < order.index(minimum_level):
        from apps.core.errors import KYCRequired

        raise KYCRequired(
            f"Verification level {minimum_level} is required for this action."
        )
