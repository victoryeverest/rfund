"""Cooperative societies (spec §35).

Cooperative savings/loans are ordinary SavingsPlan/Loan rows scoped by
cooperative — one money system, no parallel ledger (§191).
"""

from django.db import models

from apps.core.models import UUIDModel


class Cooperative(UUIDModel):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.PROTECT, related_name="cooperative"
    )
    meeting_day = models.CharField(max_length=20, blank=True, default="")
    meeting_place = models.CharField(max_length=160, blank=True, default="")
    president = models.ForeignKey(
        "customers.Customer", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    member_count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return self.organization.name


class CooperativeMember(UUIDModel):
    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        SECRETARY = "SECRETARY", "Secretary"
        TREASURER = "TREASURER", "Treasurer"
        PRESIDENT = "PRESIDENT", "President"

    cooperative = models.ForeignKey(
        Cooperative, on_delete=models.PROTECT, related_name="members"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="cooperative_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cooperative", "customer"], name="uniq_coop_member")
        ]
