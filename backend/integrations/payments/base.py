"""PaymentProvider abstraction (spec §22, §150, §151).

The application depends ONLY on this interface. Concrete adapters
(Paystack, future providers) register themselves below. Provider errors
are normalized to PaymentProviderError — Paystack specifics never leak.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from apps.core.errors import ProviderError

logger = logging.getLogger("rfund.payments")


@dataclass(frozen=True)
class InitializeResult:
    provider: str
    provider_reference: str
    authorization_url: str
    status: str  # PENDING
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VerifyResult:
    provider: str
    provider_reference: str
    amount: Decimal
    currency: str
    status: str  # SUCCESS / FAILED / PENDING
    paid_at: str | None = None
    method: str = ""
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TransferResult:
    provider: str
    provider_reference: str
    status: str  # PENDING / SUCCESS / FAILED
    raw: dict = field(default_factory=dict)


class PaymentProviderError(ProviderError):
    """Normalized provider failure (spec §151)."""

    def __init__(self, message: str, *, provider_code: str = "", provider_status: str = ""):
        super().__init__(message)
        self.provider_code = provider_code
        self.provider_status = provider_status


class PaymentProvider(Protocol):
    code: str

    def initialize_payment(
        self,
        *,
        reference: str,
        amount: Decimal,
        currency: str,
        email: str,
        callback_url: str = "",
        metadata: dict | None = None,
        channels: list[str] | None = None,
    ) -> InitializeResult: ...

    def verify_payment(self, *, provider_reference: str) -> VerifyResult: ...

    def create_transfer(
        self,
        *,
        amount: Decimal,
        currency: str,
        recipient: str,
        reason: str = "",
        reference: str = "",
    ) -> TransferResult: ...

    def verify_transfer(self, *, provider_reference: str) -> VerifyResult: ...

    def get_transaction(self, *, provider_reference: str) -> VerifyResult: ...

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool: ...


_REGISTRY: dict[str, "type[PaymentProvider]"] = {}


def register(cls):
    _REGISTRY[cls.code] = cls
    return cls


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    from django.conf import settings

    name = name or settings.PAYMENT_PROVIDER
    if name == "local":
        if not getattr(settings, "ALLOW_LOCAL_PAYMENT_PROVIDER", False):
            raise PaymentProviderError(
                "The local payment provider is not enabled. Set PAYMENT_PROVIDER "
                "and provider credentials."
            )
    if name not in _REGISTRY:
        raise PaymentProviderError(
            f"Unknown payment provider {name!r}. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()


# Import adapters so registration happens
from integrations.payments import paystack  # noqa: E402,F401
from integrations.payments import local  # noqa: E402,F401
