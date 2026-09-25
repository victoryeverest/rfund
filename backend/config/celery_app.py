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

# Periodic schedule (spec §154). apps.core.beat keeps a pure dict so this
# import stays safe before Django is ready; both the worker and the beat
# process read the schedule from the shared app config.
from apps.core.beat import BEAT_SCHEDULE  # noqa: E402

app.conf.beat_schedule = BEAT_SCHEDULE
