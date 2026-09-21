"""Celery beat schedule (spec §154). Every task idempotent."""

from __future__ import annotations

from celery.schedules import crontab

from config.celery_app import app as celery_app

celery_app.conf.beat_schedule = {
    "dispatch-outbox": {
        "task": "rfund.dispatch_outbox",
        "schedule": 30.0,
    },
    "refresh-savings-schedules": {
        "task": "rfund.refresh_savings_schedules",
        "schedule": crontab(minute=0, hour="*"),
    },
    "savings-reminders": {
        "task": "rfund.savings_reminders",
        "schedule": crontab(minute=0, hour=7),  # 07:00 UTC ≈ 08:00 Lagos
    },
    "loan-reminders": {
        "task": "rfund.loan_reminders",
        "schedule": crontab(minute=30, hour=7),
    },
    "apply-late-penalties": {
        "task": "rfund.apply_late_penalties",
        "schedule": crontab(minute=0, hour=1),
    },
    "run-reconciliation": {
        "task": "rfund.run_reconciliation",
        "schedule": crontab(minute="*/30"),
    },
    "retry-webhooks": {
        "task": "rfund.retry_webhooks",
        "schedule": crontab(minute="*/5"),
    },
    "snapshot-balances": {
        "task": "rfund.snapshot_balances",
        "schedule": crontab(minute=0, hour=2),
    },
}
