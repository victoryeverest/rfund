"""Domain error hierarchy (spec §54: structured errors, no stack traces).

Every error carries a machine-readable `code` and a user-safe `message`.
Internal details stay in the log, never in the API response.
"""

from __future__ import annotations


class RfundError(Exception):
    """Base class for all RFUND domain errors."""

    code = "DOMAIN_ERROR"
    message = "The request could not be completed."
    http_status = 400

    def __init__(self, message: str | None = None, *, code: str | None = None):
        if message:
            self.message = message
        if code:
            self.code = code
        super().__init__(self.message)


class ValidationFailed(RfundError):
    code = "VALIDATION_ERROR"
    message = "Some details you provided are not valid."
    http_status = 400


class NotFound(RfundError):
    code = "NOT_FOUND"
    message = "The requested record was not found."
    http_status = 404


class PermissionDenied(RfundError):
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."
    http_status = 403


class AuthenticationRequired(RfundError):
    code = "UNAUTHENTICATED"
    message = "Please sign in to continue."
    http_status = 401


class Conflict(RfundError):
    code = "CONFLICT"
    message = "The request conflicts with the current state."
    http_status = 409


class RateLimited(RfundError):
    code = "RATE_LIMITED"
    message = "Too many requests. Please wait a moment and try again."
    http_status = 429


class InsufficientFunds(RfundError):
    code = "INSUFFICIENT_FUNDS"
    message = "There is not enough money available to complete this transaction."
    http_status = 400


class LimitExceeded(RfundError):
    code = "LIMIT_EXCEEDED"
    message = "This transaction exceeds an applicable limit."
    http_status = 400


class KYCRequired(RfundError):
    code = "KYC_REQUIRED"
    message = "Identity verification is required before this action."
    http_status = 403


class InvalidStateTransition(RfundError):
    code = "INVALID_STATE"
    message = "This action is not available for the current status."
    http_status = 409


class IdempotencyConflict(RfundError):
    """Same idempotency key with a DIFFERENT payload — rejected loudly."""
    code = "IDEMPOTENCY_CONFLICT"
    message = "This request conflicts with an earlier request."
    http_status = 409


class ProviderError(RfundError):
    """Normalized provider failure (spec §151)."""
    code = "PROVIDER_ERROR"
    message = "A partner system could not complete the request."
    http_status = 502
