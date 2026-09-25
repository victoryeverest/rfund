"""Beat schedule wiring tests.

apps/core/beat.py was once dead configuration — never imported, so no
periodic task (outbox dispatch, schedule refresh, reconciliation, reminders)
ever ran. These tests pin the wiring: the schedule must be registered on the
Celery app and every scheduled task must exist in the worker registry.
"""

from config.celery_app import app


class TestBeatScheduleWiring:
    def test_schedule_is_registered_on_app(self):
        schedule = app.conf.beat_schedule
        assert schedule, "beat_schedule must not be empty — apps/core/beat.py wiring is broken"
        expected = {
            "dispatch-outbox",
            "refresh-savings-schedules",
            "savings-reminders",
            "loan-reminders",
            "apply-late-penalties",
            "run-reconciliation",
            "retry-webhooks",
            "snapshot-balances",
        }
        assert expected <= set(schedule.keys())

    def test_every_scheduled_task_is_registered(self):
        app.loader.import_default_modules()
        registered = set(app.tasks.keys())
        for entry in app.conf.beat_schedule.values():
            task_name = entry["task"]
            assert task_name in registered, (
                f"scheduled task {task_name} is not importable by the worker"
            )

    def test_dispatch_outbox_runs_at_short_interval(self):
        entry = app.conf.beat_schedule["dispatch-outbox"]
        assert float(entry["schedule"]) <= 60.0
