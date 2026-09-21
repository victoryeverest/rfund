from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ledger"
    verbose_name = "RFUND Ledger"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._seed_accounts, sender=self)

    def _seed_accounts(self, **kwargs):
        """Chart of accounts bootstrap (idempotent, after migrations)."""
        from apps.ledger.services import ensure_core_accounts

        ensure_core_accounts()
