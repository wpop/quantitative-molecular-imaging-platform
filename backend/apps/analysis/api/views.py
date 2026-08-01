"""Read-only viewsets for stored analysis metadata APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.analysis.api.serializers import (
    AnalysisRunSerializer,
    MeasurementResultSerializer,
)
from apps.analysis.models import AnalysisRun, MeasurementResult

if TYPE_CHECKING:
    from rest_framework.request import Request


class AnalysisRunViewSet(ReadOnlyModelViewSet[AnalysisRun]):
    """List and retrieve analysis runs already stored in PostgreSQL."""

    serializer_class = AnalysisRunSerializer
    queryset = (
        AnalysisRun.objects.select_related("study")
        .annotate(measurements_count=Count("measurements"))
        .order_by("-created_at", "id")
    )

    def get_queryset(self) -> QuerySet[AnalysisRun]:
        queryset = super().get_queryset()
        request: Request = self.request
        status = request.query_params.get("status")
        algorithm_name = request.query_params.get("algorithm_name")
        algorithm_version = request.query_params.get("algorithm_version")
        study_instance_uid = request.query_params.get("study_instance_uid")
        if status:
            queryset = queryset.filter(status=status)
        if algorithm_name:
            queryset = queryset.filter(algorithm_name=algorithm_name)
        if algorithm_version:
            queryset = queryset.filter(algorithm_version=algorithm_version)
        if study_instance_uid:
            queryset = queryset.filter(study__study_instance_uid=study_instance_uid)
        return queryset


class MeasurementResultViewSet(ReadOnlyModelViewSet[MeasurementResult]):
    """List and retrieve measurement results without running analysis."""

    serializer_class = MeasurementResultSerializer
    queryset = MeasurementResult.objects.select_related(
        "analysis_run",
        "analysis_run__study",
    ).order_by("analysis_run_id", "name", "region_label", "id")

    def get_queryset(self) -> QuerySet[MeasurementResult]:
        queryset = super().get_queryset()
        request: Request = self.request
        status = request.query_params.get("status")
        algorithm_name = request.query_params.get("algorithm_name")
        algorithm_version = request.query_params.get("algorithm_version")
        study_instance_uid = request.query_params.get("study_instance_uid")
        name = request.query_params.get("name")
        unit = request.query_params.get("unit")
        modality = request.query_params.get("modality")
        if status:
            queryset = queryset.filter(analysis_run__status=status)
        if algorithm_name:
            queryset = queryset.filter(analysis_run__algorithm_name=algorithm_name)
        if algorithm_version:
            queryset = queryset.filter(analysis_run__algorithm_version=algorithm_version)
        if study_instance_uid:
            queryset = queryset.filter(
                analysis_run__study__study_instance_uid=study_instance_uid,
            )
        if name:
            queryset = queryset.filter(name=name)
        if unit:
            queryset = queryset.filter(unit=unit)
        if modality:
            queryset = queryset.filter(metadata__modality=modality)
        return queryset
