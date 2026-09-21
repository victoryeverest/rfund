"""Middleware: request IDs and structured request logging (spec §89, §90)."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("rfund.request")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


class RequestIDMiddleware:
    """Attach a unique request id to every request/response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        set_request_id(rid)
        request.request_id = rid
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        return response


class StructuredRequestLoggingMiddleware:
    """Log one structured line per request with duration and status."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, "request_id", None):
            rid = uuid.uuid4().hex[:16]
            set_request_id(rid)
            request.request_id = rid
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        if logging.getLogger("rfund.request").isEnabledFor(logging.INFO):
            logger.info(
                "request_completed",
                extra={
                    "event": "request_completed",
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": get_request_id(),
                },
            )
        return response
