"""Private document storage (spec §62, §112).

Files live under MEDIA_ROOT (or object storage via STORAGE_BACKEND).
No public URLs are ever generated; access goes through permission-checked
endpoints issuing short-lived signed references.
"""

from django.db import models

from apps.core.models import UUIDModel


class StoredDocument(UUIDModel):
    class Kind(models.TextChoices):
        KYC_DOCUMENT = "KYC_DOCUMENT", "KYC document"
        FIELD_PHOTO = "FIELD_PHOTO", "Field verification photo"
        LOAN_DOCUMENT = "LOAN_DOCUMENT", "Loan document"
        SUPPORT_ATTACHMENT = "SUPPORT_ATTACHMENT", "Support attachment"
        REPORT_EXPORT = "REPORT_EXPORT", "Report export"

    kind = models.CharField(max_length=22, choices=Kind.choices, db_index=True)
    owner = models.ForeignKey(
        "customers.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="documents"
    )
    storage_key = models.CharField(max_length=250, unique=True)
    original_filename = models.CharField(max_length=200, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, default="")
    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
