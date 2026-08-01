"""Admin registrations for quantitative analysis models."""

from django.contrib import admin

from .models import AnalysisRun, MeasurementResult


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "study",
        "algorithm_name",
        "algorithm_version",
        "status",
        "created_at",
    )
    list_filter = ("status", "algorithm_name", "created_at")
    search_fields = (
        "name",
        "algorithm_name",
        "algorithm_version",
        "study__study_instance_uid",
    )


@admin.register(MeasurementResult)
class MeasurementResultAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "analysis_run", "value", "unit", "region_label", "created_at")
    list_filter = ("unit", "region_label", "created_at")
    search_fields = ("name", "unit", "region_label", "analysis_run__name")
