from django.apps import AppConfig


class HotelCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hotel_core"

    def ready(self):
        import hotel_core.signals # Connect signals
