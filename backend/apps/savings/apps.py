from django.apps import AppConfig


class SavingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.savings"
    verbose_name = "RFUND Savings"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._seed_products, sender=self)

    def _seed_products(self, **kwargs):
        """Idempotent reference-data bootstrap (after migrations)."""
        from apps.savings.services import ensure_default_products

        ensure_default_products()
