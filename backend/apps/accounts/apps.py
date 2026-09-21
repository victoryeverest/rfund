from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "RFUND Accounts"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(self._seed_rbac, sender=self)

    def _seed_rbac(self, **kwargs):
        """Idempotent role/permission bootstrap (runs after migrations)."""
        from apps.accounts.services import bootstrap_rbac

        bootstrap_rbac()
