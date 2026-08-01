"""Admin registrations for ingestion workflow models."""

from django.contrib import admin

from .models import IngestionJob, IngestionJobEvent


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "source_name",
        "source_type",
        "status",
        "started_at",
        "completed_at",
        "created_at",
    )
    list_filter = ("status", "source_type", "created_at")
    search_fields = ("source_name", "source_uri")


@admin.register(IngestionJobEvent)
class IngestionJobEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("job", "level", "created_at", "message")
    list_filter = ("level", "created_at")
    search_fields = ("message", "job__source_name")
