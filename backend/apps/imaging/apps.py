"""Django application configuration for imaging data management."""

from django.apps import AppConfig


class ImagingConfig(AppConfig):
    """Configure the imaging application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.imaging"
    verbose_name = "Imaging"
