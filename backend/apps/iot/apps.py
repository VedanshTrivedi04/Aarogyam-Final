from django.apps import AppConfig

class IotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.iot'
    label = 'iot'

    def ready(self):
        from . import signals  # noqa: F401
