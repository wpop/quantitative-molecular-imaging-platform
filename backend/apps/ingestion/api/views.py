"""Read-only viewsets for ingestion metadata APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.ingestion.api.serializers import (
    IngestionJobEventSerializer,
    IngestionJobSerializer,
)
from apps.ingestion.models import IngestionJob, IngestionJobEvent

if TYPE_CHECKING:
    from rest_framework.request import Request


class IngestionJobViewSet(ReadOnlyModelViewSet[IngestionJob]):
    """List and retrieve ingestion job metadata."""

    serializer_class = IngestionJobSerializer
    queryset = IngestionJob.objects.annotate(event_count=Count("events")).order_by(
        "-created_at",
        "id",
    )

    def get_queryset(self) -> QuerySet[IngestionJob]:
        queryset = super().get_queryset()
        request: Request = self.request
        status = request.query_params.get("status")
        source_type = request.query_params.get("source_type")
        source_name = request.query_params.get("source_name")
        if status:
            queryset = queryset.filter(status=status)
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        if source_name:
            queryset = queryset.filter(source_name=source_name)
        return queryset


class IngestionJobEventViewSet(ReadOnlyModelViewSet[IngestionJobEvent]):
    """List and retrieve ingestion job event metadata."""

    serializer_class = IngestionJobEventSerializer
    queryset = IngestionJobEvent.objects.select_related("job").order_by(
        "-created_at",
        "-id",
    )

    def get_queryset(self) -> QuerySet[IngestionJobEvent]:
        queryset = super().get_queryset()
        request: Request = self.request
        job = request.query_params.get("job")
        level = request.query_params.get("level")
        if job:
            try:
                job_id = int(job)
            except ValueError:
                return queryset.none()
            queryset = queryset.filter(job_id=job_id)
        if level:
            queryset = queryset.filter(level=level)
        return queryset
