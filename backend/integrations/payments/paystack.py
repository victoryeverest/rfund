"""Paystack payment provider adapter (spec §23).

- Secrets ONLY from environment (PAYSTACK_SECRET_KEY / WEBHOOK_SECRET)
- Server-side verification is authoritative — the browser's claim is never
  trusted (§23)
- Webhook signature: HMAC-SHA512 of the raw body with the secret
- All errors normalized to PaymentProviderError (§151)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal

import httpx
from django.conf import settings

from integrations.payments.base import (
    InitializeResult,
    PaymentProviderError,
    TransferResult,
    VerifyResult,
    register,
)

logger = logging.getLogger("rfund.payments.paystack")


@register
class PaystackProvider:
    code = "paystack"

    def _client(self) -> httpx.Client:
        if not settings.PAYSTACK_SECRET_KEY:
            raise PaymentProviderError(
                "PAYSTACK_SECRET_KEY is not configured.",
                provider_code="missing_credentials",
            )
        return httpx.Client(
            base_url=settings.PAYSTACK_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=settings.PAYSTACK_TIMEOUT_SECONDS,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with self._client() as client:
                response = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            logger.warning(
                "paystack_network_error",
                extra={"provider": "paystack", "error_code": type(exc).__name__},
            )
            raise PaymentProviderError(
                "The payment provider could not be reached.",
                provider_code="network",
            ) from exc
        if response.status_code >= 500:
            raise PaymentProviderError(
                "The payment provider had a server error.",
                provider_code="provider_5xx",
                provider_status=str(response.status_code),
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise PaymentProviderError(
                "The payment provider returned an unreadable response.",
                provider_code="bad_response",
            ) from exc
        if not response.is_success:
            raise PaymentProviderError(
                "The payment provider rejected the request.",
                provider_code=body.get("code") or "provider_error",
                provider_status=str(response.status_code),
            )
        return body

    # -- Interface methods ---------------------------------------------------
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
        if currency != "NGN":
            # Paystack supports others for some merchants; keep NGN-first and
            # make any change explicit rather than silent.
            raise PaymentProviderError(
                "Only NGN is configured for Paystack on this deployment.",
                provider_code="currency",
            )
        payload = {
            "reference": reference,
            "amount": int((amount * 100).quantize(Decimal("1"))),  # kobo
            "email": email or "payments@rfund.example",
            "currency": "NGN",
            "metadata": metadata or {},
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if channels:
            payload["channels"] = channels
        body = self._request("POST", "/transaction/initialize", json=payload)
        data = body.get("data") or {}
        return InitializeResult(
            provider=self.code,
            provider_reference=data.get("reference", reference),
            authorization_url=data.get("authorization_url", ""),
            status="PENDING",
            raw=body,
        )

    def verify_payment(self, *, provider_reference: str) -> VerifyResult:
        return self._fetch_transaction(provider_reference)

    def get_transaction(self, *, provider_reference: str) -> VerifyResult:
        return self._fetch_transaction(provider_reference)

    def _fetch_transaction(self, provider_reference: str) -> VerifyResult:
        body = self._request("GET", f"/transaction/verify/{provider_reference}")
        data = body.get("data") or {}
        status = str(data.get("status", "")).upper()  # abandoned/failed/success
        amount_major = Decimal(str(data.get("amount", 0))) / 100
        method = ""
        channel = data.get("channel") or ""
        if channel:
            method = str(channel).upper()[:16]
        return VerifyResult(
            provider=self.code,
            provider_reference=str(data.get("reference", provider_reference)),
            amount=amount_major,
            currency=str(data.get("currency", "NGN")),
            status="SUCCESS" if status == "SUCCESS" else ("FAILED" if status in ("FAILED", "ABANDONED") else "PENDING"),
            paid_at=data.get("paid_at"),
            method=method,
            raw=body,
        )

    def create_transfer(
        self,
        *,
        amount: Decimal,
        currency: str,
        recipient: str,
        reason: str = "",
        reference: str = "",
    ) -> TransferResult:
        payload = {
            "amount": int((amount * 100).quantize(Decimal("1"))),
            "recipient": recipient,
            "reason": reason[:100],
            "currency": currency,
        }
        if reference:
            payload["reference"] = reference
        body = self._request("POST", "/transfer", json=payload)
        data = body.get("data") or {}
        return TransferResult(
            provider=self.code,
            provider_reference=str(data.get("reference") or data.get("id", "")),
            status="PENDING",  # Paystack transfers are async
            raw=body,
        )

    def verify_transfer(self, *, provider_reference: str) -> VerifyResult:
        body = self._request("GET", f"/transfer/verify/{provider_reference}")
        data = body.get("data") or {}
        status = str(data.get("status", "")).upper()
        amount_major = Decimal(str(data.get("amount", 0))) / 100
        return VerifyResult(
            provider=self.code,
            provider_reference=str(data.get("reference", provider_reference)),
            amount=amount_major,
            currency=str(data.get("currency", "NGN")),
            status="SUCCESS" if status == "SUCCESS" else ("FAILED" if status in ("FAILED", "REVERSED") else "PENDING"),
            raw=body,
        )

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool:
        if not settings.PAYSTACK_WEBHOOK_SECRET:
            logger.error("paystack_webhook_secret_missing")
            return False
        expected = hmac.new(
            settings.PAYSTACK_WEBHOOK_SECRET.encode(), payload_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
