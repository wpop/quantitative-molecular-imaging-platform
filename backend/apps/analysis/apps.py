"""Django application configuration for quantitative analysis workflows."""

from django.apps import AppConfig


class AnalysisConfig(AppConfig):
    """Configure the analysis application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analysis"
    verbose_name = "Quantitative Analysis"
