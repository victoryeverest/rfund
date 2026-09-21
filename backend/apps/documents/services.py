"""Document upload + private retrieval (spec §62, §112)."""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from apps.core.errors import PermissionDenied, ValidationFailed
from apps.documents.models import StoredDocument


def _extension_ok(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in settings.ALLOWED_UPLOAD_EXTENSIONS


def upload_document(
    *, kind: str, uploaded_file, owner=None, uploaded_by=None,
    max_bytes: int | None = None,
) -> StoredDocument:
    max_bytes = max_bytes or settings.MAX_UPLOAD_BYTES
    if uploaded_file.size > max_bytes:
        raise ValidationFailed(
            f"File is too large. Maximum {max_bytes // (1024 * 1024)} MB."
        )
    if not _extension_ok(uploaded_file.name):
        raise ValidationFailed(
            f"Allowed file types: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
        )
    content = uploaded_file.read()
    checksum = hashlib.sha256(content).hexdigest()
    ext = Path(uploaded_file.name).suffix.lower().lstrip(".")
    # Server-generated names only — never trust client filenames (§112)
    storage_key = f"{kind.lower()}/{secrets.token_hex(16)}.{ext}"
    from django.core.files.storage import default_storage

    saved_name = default_storage.save(storage_key, ContentFile(content))
    doc = StoredDocument.objects.create(
        kind=kind,
        owner=owner,
        storage_key=saved_name,
        original_filename=Path(uploaded_file.name).name[:200],
        content_type=getattr(uploaded_file, "content_type", "") or "",
        size_bytes=len(content),
        checksum=checksum,
        uploaded_by=uploaded_by,
    )
    return doc


def read_document(doc: StoredDocument, *, requested_by) -> bytes:
    """Permission-checked read. KYC documents need kyc.read/document.read."""
    if doc.owner is not None:
        is_owner = requested_by is not None and doc.owner.user_id == requested_by.pk
        has_staff_perm = requested_by is not None and (
            requested_by.has_perm_code("document.read")
            or requested_by.has_perm_code("kyc.read")
        )
        if not (is_owner or has_staff_perm):
            raise PermissionDenied("You cannot access this document.")
    from django.core.files.storage import default_storage

    with default_storage.open(doc.storage_key, "rb") as f:
        return f.read()
