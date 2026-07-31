"""Django application configuration for DICOM ingestion workflows."""

from django.apps import AppConfig


class IngestionConfig(AppConfig):
    """Configure the ingestion application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ingestion"
    verbose_name = "Data Ingestion"
