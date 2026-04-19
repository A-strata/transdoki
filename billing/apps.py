from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Биллинг"

    def ready(self):
        # noqa: F401 — импорт регистрирует receivers
        from billing import signals  # noqa: F401
