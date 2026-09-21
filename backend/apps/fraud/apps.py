from django.apps import AppConfig


class FraudConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fraud"
    verbose_name = "RFUND Fraud"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._seed_rules, sender=self)

    def _seed_rules(self, **kwargs):
        """Idempotent reference-data bootstrap (after migrations)."""
        from apps.fraud.services import ensure_default_rules

        ensure_default_rules()
