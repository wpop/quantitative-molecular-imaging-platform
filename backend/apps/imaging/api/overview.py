"""Read-only overview endpoint for ingested metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy
from apps.ingestion.models import IngestionJob

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request


def ordered_values(queryset: QuerySet[Any], field_name: str) -> list[str]:
    """Return deterministic non-empty string values for overview lists."""
    return list(
        queryset.exclude(**{field_name: ""})
        .values_list(field_name, flat=True)
        .distinct()
        .order_by(field_name),
    )


class MetadataOverviewView(APIView):
    """Return a compact metadata-only summary for dashboard use."""

    def get(self, _request: Request) -> Response:
        latest_job = IngestionJob.objects.order_by("-started_at", "-created_at").first()
        return Response(
            {
                "studies_count": ImagingStudy.objects.count(),
                "series_count": ImagingSeries.objects.count(),
                "instances_count": ImagingInstance.objects.count(),
                "modalities": ordered_values(ImagingSeries.objects.all(), "modality"),
                "source_datasets": ordered_values(ImagingStudy.objects.all(), "source_dataset"),
                "source_subjects": ordered_values(ImagingStudy.objects.all(), "source_subject_id"),
                "ingestion_jobs_count": IngestionJob.objects.count(),
                "latest_ingestion_status": latest_job.status if latest_job else None,
                "latest_ingestion_started_at": latest_job.started_at if latest_job else None,
                "latest_ingestion_completed_at": latest_job.completed_at if latest_job else None,
            },
        )
