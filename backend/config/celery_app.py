"""Celery application for RFUND (spec §153, §154).

Financial truth always lives in PostgreSQL. Celery handles asynchronous
delivery: notifications (outbox), webhook processing, reconciliation,
reminders, reports. Tasks must be idempotent.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("rfund")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
