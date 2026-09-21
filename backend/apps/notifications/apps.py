from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "RFUND Notifications"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._seed_templates, sender=self)

    def _seed_templates(self, **kwargs):
        """Idempotent reference-data bootstrap (after migrations)."""
        from apps.notifications.services import ensure_default_templates

        ensure_default_templates()
