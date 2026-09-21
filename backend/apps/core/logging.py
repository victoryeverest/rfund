"""Structured JSON logging (spec §89).

Never logged (enforced by convention + reviews + tests):
passwords, OTPs, payment secrets, full identity numbers, API keys.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from apps.core.middleware import get_request_id

REDACTED_FIELDS = {
    "password", "pin", "otp", "code", "secret", "token", "authorization",
    "secret_key", "paystack_secret_key", "sms_provider_key", "bvn", "nin",
    "id_number", "provider_secret",
}


def _scrub(value):
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if str(k).lower() in REDACTED_FIELDS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        extra = getattr(record, "event", None)
        if extra and isinstance(extra, str):
            payload["event"] = extra
        for key in (
            "operation", "status", "duration_ms", "user_id", "method", "path",
            "reference", "transaction_reference", "actor", "action", "resource",
            "provider", "event_id", "error_code",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        structured = getattr(record, "structured", None)
        if structured:
            payload["data"] = _scrub(structured)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestIDLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True
