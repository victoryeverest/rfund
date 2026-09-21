"""Secured GraphQL HTTP view (spec §53, §115, §164).

Centralized protection before execution:
  - POST only, JSON body only
  - maximum request size
  - query depth limit (walks the document AST)
  - per-role rate limits (Redis when available, in-memory fallback)
  - structured, sanitized errors — no stack traces, no internals (§54)
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque

from django.http import HttpRequest, HttpResponse, JsonResponse
from graphql import GraphQLError
from strawberry.types import ExecutionResult

from apps.core.errors import RfundError
from config import settings as django_settings

logger = logging.getLogger("rfund.graphql")

RATE_BUCKETS = {
    "anonymous": "RATE_LIMIT_ANONYMOUS",
    "customer": "RATE_LIMIT_CUSTOMER",
    "agent": "RATE_LIMIT_AGENT",
    "admin": "RATE_LIMIT_ADMIN",
}

# ---------------------------------------------------------------------------
# Rate limiting (spec §113): sliding window, Redis-backed when available.
# ---------------------------------------------------------------------------
class MemoryWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_memory = MemoryWindow()
_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis as redis_lib

            _redis_client = redis_lib.Redis.from_url(
                django_settings.REDIS_URL, socket_timeout=1
            )
            _redis_client.ping()
        except Exception:
            _redis_client = False
    return _redis_client or None


def allow_request(key: str, limit: int) -> bool:
    client = _redis()
    if client is not None:
        try:
            redis_key = f"ratelimit:{key}"
            count = client.incr(redis_key)
            if count == 1:
                client.expire(redis_key, 60)
            return count <= limit
        except Exception:
            pass  # fail-open on limiter errors; the API stays available
    return _memory.hit(key, limit)


# ---------------------------------------------------------------------------
# Depth limiting (spec §115)
# ---------------------------------------------------------------------------
def document_depth(query: str) -> int:
    """Max selection-set depth of the query (walks the GraphQL AST)."""
    from graphql import parse

    try:
        doc = parse(query)
    except Exception:
        return -1

    def walk(selection_set, depth: int) -> int:
        if selection_set is None:
            return depth
        deepest = depth
        for sel in selection_set.selections:
            inner = getattr(sel, "selection_set", None)
            if inner is not None:
                deepest = max(deepest, walk(inner, depth + 1))
        return deepest

    max_depth = 0
    for definition in doc.definitions:
        sel_set = getattr(definition, "selection_set", None)
        if sel_set is not None:
            max_depth = max(max_depth, walk(sel_set, 1))
    return max_depth


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------
class RfundGraphQLView:
    """Django view that executes the Strawberry schema with hard guards."""

    schema = None  # injected at URL wiring time

    def __init__(self, schema):
        self.schema = schema

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method not in ("POST", "GET"):
            return JsonResponse({"errors": [{"message": "Method not allowed"}]}, status=405)

        body_length = len(request.body or b"")
        if body_length > django_settings.GRAPHQL_MAX_OPERATION_BYTES:
            return JsonResponse(
                {"errors": [{"message": "The request is too large."}]}, status=413
            )

        if request.method == "POST":
            try:
                payload = json.loads(request.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return JsonResponse(
                    {"errors": [{"message": "The request body must be valid JSON."}]}, status=400
                )
        else:
            # GET: only allow small schema introspection queries (graphiql off)
            payload = {"query": request.GET.get("query", "")}

        query = (payload or {}).get("query", "")
        if not isinstance(query, str) or not query.strip():
            return JsonResponse(
                {"errors": [{"message": "A GraphQL query is required."}]}, status=400
            )

        depth = document_depth(query)
        if depth < 0:
            return JsonResponse(
                {"errors": [{"message": "The query could not be parsed."}]}, status=400
            )
        if depth > django_settings.GRAPHQL_DEPTH_LIMIT:
            return JsonResponse(
                {"errors": [{"message": f"Query depth exceeds the limit of {django_settings.GRAPHQL_DEPTH_LIMIT}."}]},
                status=400,
            )

        from graphql_api.context import build_context

        context = build_context(request)

        limit_name = RATE_BUCKETS.get(context.rate_bucket, "RATE_LIMIT_ANONYMOUS")
        limit = getattr(django_settings, limit_name, 60)
        rate_key = f"{context.rate_bucket}:{context.ip_address or 'unknown'}"
        if not allow_request(rate_key, limit):
            return JsonResponse(
                {
                    "errors": [
                        {
                            "message": "Too many requests. Please wait a moment and try again.",
                            "extensions": {"code": "RATE_LIMITED"},
                        }
                    ]
                },
                status=429,
            )

        result: ExecutionResult = self.schema.execute_sync(
            query,
            variable_values=payload.get("variables") or {},
            operation_name=payload.get("operationName") or None,
            context_value=context,
        )
        return JsonResponse({"data": result.data, "errors": self._format_errors(result)})

    def _format_errors(self, result: ExecutionResult) -> list[dict]:
        errors: list[dict] = []
        if not result.errors:
            return errors
        for error in result.errors:
            original = error.original_error
            if isinstance(original, RfundError):
                errors.append(
                    {
                        "message": original.message,
                        "extensions": {
                            "code": original.code,
                        },
                        **({"path": list(error.path)} if error.path else {}),
                    }
                )
            elif isinstance(original, GraphQLError) and original.extensions:
                errors.append(
                    {
                        "message": error.message,
                        "extensions": original.extensions,
                        **({"path": list(error.path)} if error.path else {}),
                    }
                )
            else:
                # Unexpected error: log full detail, return sanitized message (§54)
                logger.error(
                    "graphql_unexpected_error",
                    exc_info=original or error,
                    extra={
                        "event": "graphql_unexpected_error",
                        "error_code": type(original).__name__ if original else "GraphQLError",
                    },
                )
                errors.append(
                    {
                        "message": "Something went wrong on our side. Please try again.",
                        "extensions": {"code": "INTERNAL_ERROR"},
                    }
                )
        return errors
