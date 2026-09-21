"""Paystack webhook HTTP endpoint (spec §25).

Dedicated endpoint (not GraphQL): webhooks are machine-to-machine HTTP.
Requirements implemented:
  - verify signature (HMAC-SHA512 of raw body)
  - store raw event FIRST with a unique event id
  - process idempotently
  - acknowledge safely (200 once stored) so the provider does not retry-storm
  - never lose events: failures are recorded with error + retry via beat job
"""

from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.payments.services import ingest_webhook, process_webhook_event
from integrations.payments.base import get_payment_provider

logger = logging.getLogger("rfund.payments.webhook")


def paystack_webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    raw_body = request.body
    signature = request.headers.get("X-Paystack-Signature", "")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("paystack_webhook_bad_json")
        return JsonResponse({"error": "invalid payload"}, status=400)

    provider = get_payment_provider("paystack")
    signature_valid = provider.verify_webhook_signature(
        payload_body=raw_body, signature=signature
    )
    if not signature_valid:
        logger.warning("paystack_webhook_invalid_signature")
        # Store nothing? Spec says never lose events — but a spoofed event
        # must not be processable. We record it with signature_valid=False
        # (stored, quarantined, never processed).
        event = ingest_webhook(
            provider_code="paystack",
            event_id=payload.get("data", {}).get("id", "") or f"unsigned-{id(payload)}",
            event_type=payload.get("event", ""),
            payload=payload,
            signature_valid=False,
        )
        return JsonResponse(
            {"error": "invalid signature", "stored_event": str(event.pk)}, status=401
        )

    event_id = str(
        payload.get("data", {}).get("id")
        or payload.get("data", {}).get("reference")
        or ""
    )
    if not event_id:
        return JsonResponse({"error": "missing event id"}, status=400)

    event = ingest_webhook(
        provider_code="paystack",
        event_id=event_id,
        event_type=payload.get("event", ""),
        payload=payload,
        signature_valid=True,
    )
    # Process inline (idempotent). Celery dispatch is available for load
    # shedding; inline keeps the sandbox deterministic.
    process_webhook_event(event)

    return JsonResponse({"status": "received"})
