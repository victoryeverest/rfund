"""Support system (spec §51)."""

from django.db import models

from apps.core.models import UUIDModel


class SupportTicket(UUIDModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        WAITING_CUSTOMER = "WAITING_CUSTOMER", "Waiting on customer"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Category(models.TextChoices):
        MISSING_PAYMENT = "MISSING_PAYMENT", "Missing payment"
        INCORRECT_BALANCE = "INCORRECT_BALANCE", "Incorrect balance"
        FAILED_LOAN = "FAILED_LOAN", "Loan problem"
        ACCOUNT_PROBLEM = "ACCOUNT_PROBLEM", "Account problem"
        AGENT_COMPLAINT = "AGENT_COMPLAINT", "Agent complaint"
        TRANSACTION_ISSUE = "TRANSACTION_ISSUE", "Transaction issue"
        OTHER = "OTHER", "Other"

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="support_tickets"
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    assignee = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_tickets"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class SupportMessage(UUIDModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name="messages")
    sender = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    body = models.TextField()
    internal = models.BooleanField(default=False)  # staff-only note
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
