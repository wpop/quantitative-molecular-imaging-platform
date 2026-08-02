"""Read-only viewsets for stored analysis metadata APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.db.models import Count, QuerySet
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.analysis.api.artifact_files import resolve_visualization_artifact_path
from apps.analysis.api.serializers import (
    AnalysisRunSerializer,
    MeasurementResultSerializer,
    VisualizationArtifactSerializer,
    VisualizationExecutionRequestSerializer,
)
from apps.analysis.models import AnalysisRun, MeasurementResult, VisualizationArtifact
from apps.analysis.visualization_execution import (
    VisualizationExecutionError,
    execute_visualization_request,
)

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


class VisualizationArtifactViewSet(ReadOnlyModelViewSet[VisualizationArtifact]):
    """List, retrieve, and safely serve registered visualization artifacts."""

    serializer_class = VisualizationArtifactSerializer
    queryset = VisualizationArtifact.objects.select_related(
        "instance",
        "instance__series",
        "instance__series__study",
    ).order_by("-created_at", "id")

    def get_queryset(self) -> QuerySet[VisualizationArtifact]:
        queryset = super().get_queryset()
        request: Request = self.request
        series_instance_uid = request.query_params.get("series_instance_uid")
        sop_instance_uid = request.query_params.get("sop_instance_uid")
        operation = request.query_params.get("operation")
        modality = request.query_params.get("modality")
        if series_instance_uid:
            queryset = queryset.filter(instance__series__series_instance_uid=series_instance_uid)
        if sop_instance_uid:
            queryset = queryset.filter(instance__sop_instance_uid=sop_instance_uid)
        if operation:
            queryset = queryset.filter(operation=operation)
        if modality:
            queryset = queryset.filter(modality=modality)
        return queryset

    @action(detail=True, methods=["get"], url_path="image")
    def image(self, request: Request, pk: str | None = None) -> FileResponse:
        del request, pk
        artifact = self.get_object()
        image_path = resolve_visualization_artifact_path(artifact.relative_path)
        return FileResponse(
            image_path.open("rb"),
            content_type="image/png",
            as_attachment=False,
            filename=image_path.name,
        )


class VisualizationArtifactGenerateView(APIView):
    """Generate and register one visualization artifact through controlled parameters."""

    def post(self, request: Request) -> Response:
        request_serializer = VisualizationExecutionRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data

        try:
            artifact = execute_visualization_request(
                series_instance_uid=cast("str", data["series_instance_uid"]),
                operation=cast("str", data["operation"]),
                slice_index=cast("int | None", data.get("slice_index")),
                gaussian_sigma=cast("float", data.get("gaussian_sigma", 1.0)),
                window_center=cast("float | None", data.get("window_center")),
                window_width=cast("float | None", data.get("window_width")),
                lower_percentile=cast("float", data.get("lower_percentile", 1.0)),
                upper_percentile=cast("float", data.get("upper_percentile", 99.0)),
                dpi=cast("int", data.get("dpi", 150)),
            )
        except VisualizationExecutionError as exc:
            response_status = (
                status.HTTP_404_NOT_FOUND
                if exc.series_selection_failed
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": exc.public_message}, status=response_status)

        response_serializer = VisualizationArtifactSerializer(
            artifact,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
