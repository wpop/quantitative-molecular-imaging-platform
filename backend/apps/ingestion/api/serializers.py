"""Serializers for read-only ingestion metadata APIs."""

from rest_framework import serializers

from apps.ingestion.models import IngestionJob, IngestionJobEvent


class IngestionJobSerializer(serializers.ModelSerializer[IngestionJob]):
    """Expose ingestion job metadata."""

    event_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = IngestionJob
        fields = (
            "id",
            "status",
            "source_type",
            "source_name",
            "started_at",
            "completed_at",
            "error_message",
            "event_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class IngestionJobEventSerializer(serializers.ModelSerializer[IngestionJobEvent]):
    """Expose structured ingestion event metadata."""

    class Meta:
        model = IngestionJobEvent
        fields = (
            "id",
            "job",
            "level",
            "message",
            "context",
            "created_at",
        )
        read_only_fields = fields
