"""Deterministic LOCAL payment provider — development and test ONLY (spec §102).

This is NOT fake success in production: it cannot be selected when
DJANGO_ENV=production (refused in settings and in the registry lookup).

It simulates a real provider's async lifecycle deterministically:
initialize → PENDING; verify → SUCCESS (or FAILED on demand); webhook
events carry the same shapes Paystack sends so the whole pipeline
(webhook signature, idempotent processing, ledger posting) is exercised
end-to-end without external network access.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from decimal import Decimal

from django.conf import settings

from integrations.payments.base import (
    InitializeResult,
    PaymentProviderError,
    TransferResult,
    VerifyResult,
    register,
)


@register
class LocalProvider:
    code = "local"

    # In-memory simulation state (test/development only)
    _state: dict[str, dict] = {}

    def _secret(self) -> str:
        return settings.PAYSTACK_WEBHOOK_SECRET or "local-dev-webhook-secret"

    def initialize_payment(
        self,
        *,
        reference: str,
        amount: Decimal,
        currency: str = "NGN",
        email: str = "",
        callback_url: str = "",
        metadata: dict | None = None,
        channels: list[str] | None = None,
    ) -> InitializeResult:
        provider_reference = f"localpay_{secrets.token_hex(8)}"
        self._state[provider_reference] = {
            "reference": reference,
            "amount": str(amount),
            "currency": currency,
            "status": "PENDING",
            "fail": (metadata or {}).get("simulate", "") == "fail",
        }
        return InitializeResult(
            provider=self.code,
            provider_reference=provider_reference,
            authorization_url=f"/payments/local/checkout?ref={provider_reference}",
            status="PENDING",
            raw={"simulated": True},
        )

    def _find(self, provider_reference: str) -> dict:
        if provider_reference in self._state:
            return self._state[provider_reference]
        # Deterministic fallback for references created in earlier processes
        # (e.g. seed data): derive amount from the reference itself is unsafe;
        # treat unknown references as failed lookups like a real provider.
        raise PaymentProviderError(
            "Transaction not found.", provider_code="not_found", provider_status="404"
        )

    def verify_payment(self, *, provider_reference: str) -> VerifyResult:
        item = self._find(provider_reference)
        status = "SUCCESS" if not item.get("fail") else "FAILED"
        return VerifyResult(
            provider=self.code,
            provider_reference=provider_reference,
            amount=Decimal(item["amount"]),
            currency=item["currency"],
            status=status,
            method="CARD",
            raw={"simulated": True, "internal_reference": item["reference"]},
        )

    get_transaction = verify_payment

    def create_transfer(
        self,
        *,
        amount: Decimal,
        currency: str,
        recipient: str,
        reason: str = "",
        reference: str = "",
    ) -> TransferResult:
        provider_reference = f"localxfer_{secrets.token_hex(8)}"
        self._state[provider_reference] = {
            "reference": reference,
            "amount": str(amount),
            "currency": currency,
            "status": "PENDING",
        }
        return TransferResult(
            provider=self.code,
            provider_reference=provider_reference,
            status="PENDING",
            raw={"simulated": True},
        )

    def verify_transfer(self, *, provider_reference: str) -> VerifyResult:
        item = self._find(provider_reference)
        return VerifyResult(
            provider=self.code,
            provider_reference=provider_reference,
            amount=Decimal(item["amount"]),
            currency=item["currency"],
            status="SUCCESS",
            raw={"simulated": True},
        )

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool:
        expected = hmac.new(
            self._secret().encode(), payload_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    # -- Test/seed helpers ---------------------------------------------------
    def sign(self, payload: dict) -> str:
        return hmac.new(
            self._secret().encode(),
            json.dumps(payload).encode(),
            hashlib.sha512,
        ).hexdigest()

    def mark_success(self, provider_reference: str) -> dict:
        """Build the provider 'charge.success' webhook payload."""
        item = self._find(provider_reference)
        return {
            "event": "charge.success",
            "data": {
                "id": int(secrets.token_hex(6), 16),
                "reference": provider_reference,
                "amount": int(Decimal(item["amount"]) * 100),
                "currency": item["currency"],
                "status": "success",
                "paid_at": "2026-01-01T10:00:00.000Z",
                "channel": "card",
                "metadata": {"internal_reference": item["reference"]},
            },
        }
