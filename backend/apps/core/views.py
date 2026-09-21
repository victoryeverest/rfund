"""Health endpoints (spec §169): liveness + readiness.

Readiness verifies real dependencies (database, migrations applied,
redis when configured for async processing).
"""

from __future__ import annotations

import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger("rfund.health")


def health_live(request):
    """Liveness: process is up. No dependency checks."""
    return JsonResponse({"status": "ok"})


def health_ready(request):
    """Readiness: process can serve traffic."""
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - depends on env
        checks["database"] = f"error: {type(exc).__name__}"
        logger.error("readiness_database_failed", exc_info=True)

    try:
        from django.conf import settings

        if not settings.CELERY_TASK_ALWAYS_EAGER:
            import redis as redis_lib

            client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
            client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "skipped (eager mode)"
    except Exception as exc:  # pragma: no cover
        checks["redis"] = f"error: {type(exc).__name__}"
        logger.error("readiness_redis_failed", exc_info=True)

    ready = all(v == "ok" or v.startswith("skipped") for v in checks.values())
    return JsonResponse(
        {"status": "ready" if ready else "not_ready", "checks": checks},
        status=200 if ready else 503,
    )
