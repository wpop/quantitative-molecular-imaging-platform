"""Serializers for read-only analysis metadata APIs."""

from collections.abc import Mapping
from typing import cast

from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.analysis.models import AnalysisRun, MeasurementResult, VisualizationArtifact
from apps.analysis.scientific_operations import ScientificOperation

MAX_PERCENTILE = 100.0


class AnalysisRunSerializer(serializers.ModelSerializer[AnalysisRun]):
    """Expose stored analysis run metadata."""

    study_instance_uid = serializers.CharField(source="study.study_instance_uid", read_only=True)
    measurements_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AnalysisRun
        fields = (
            "id",
            "study",
            "study_instance_uid",
            "status",
            "name",
            "algorithm_name",
            "algorithm_version",
            "parameters",
            "started_at",
            "completed_at",
            "error_message",
            "measurements_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MeasurementResultSerializer(serializers.ModelSerializer[MeasurementResult]):
    """Expose quantitative measurement metadata stored in PostgreSQL."""

    analysis_run_id = serializers.IntegerField(source="analysis_run.id", read_only=True)
    algorithm_name = serializers.CharField(source="analysis_run.algorithm_name", read_only=True)
    algorithm_version = serializers.CharField(
        source="analysis_run.algorithm_version",
        read_only=True,
    )
    study_instance_uid = serializers.CharField(
        source="analysis_run.study.study_instance_uid",
        read_only=True,
    )

    class Meta:
        model = MeasurementResult
        fields = (
            "id",
            "analysis_run",
            "analysis_run_id",
            "algorithm_name",
            "algorithm_version",
            "study_instance_uid",
            "name",
            "value",
            "unit",
            "region_label",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class VisualizationArtifactSerializer(serializers.ModelSerializer[VisualizationArtifact]):
    """Expose visualization artifact metadata without local filesystem paths."""

    instance_id = serializers.IntegerField(source="instance.id", read_only=True)
    sop_instance_uid = serializers.CharField(source="instance.sop_instance_uid", read_only=True)
    series_instance_uid = serializers.CharField(
        source="instance.series.series_instance_uid",
        read_only=True,
    )
    study_instance_uid = serializers.CharField(
        source="instance.series.study.study_instance_uid",
        read_only=True,
    )
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = VisualizationArtifact
        fields = (
            "id",
            "instance_id",
            "sop_instance_uid",
            "series_instance_uid",
            "study_instance_uid",
            "operation",
            "modality",
            "slice_index",
            "value_units",
            "rows",
            "columns",
            "colormap",
            "display_minimum",
            "display_maximum",
            "window_center",
            "window_width",
            "mime_type",
            "file_size_bytes",
            "file_sha256",
            "created_at",
            "updated_at",
            "image_url",
        )
        read_only_fields = fields

    def get_image_url(self, artifact: VisualizationArtifact) -> str:
        request = self.context.get("request")
        return reverse(
            "analysis-api:visualization-artifact-image",
            kwargs={"pk": artifact.pk},
            request=request if request is not None else None,
        )


class VisualizationExecutionRequestSerializer(serializers.Serializer[dict[str, object]]):
    """Validate requests for controlled visualization artifact generation."""

    series_instance_uid = serializers.CharField(required=True, allow_blank=False)
    operation = serializers.ChoiceField(
        required=True,
        choices=[operation.value for operation in ScientificOperation],
    )
    slice_index = serializers.IntegerField(required=False, min_value=0)
    gaussian_sigma = serializers.FloatField(required=False, min_value=0.0)
    window_center = serializers.FloatField(required=False)
    window_width = serializers.FloatField(required=False, min_value=0.0)
    lower_percentile = serializers.FloatField(required=False)
    upper_percentile = serializers.FloatField(required=False)
    dpi = serializers.IntegerField(required=False, min_value=1)

    def to_internal_value(self, data: object) -> dict[str, object]:
        if isinstance(data, Mapping):
            unsupported_fields = sorted(str(key) for key in data if str(key) not in self.fields)
            if unsupported_fields:
                message = "Unsupported field."
                raise serializers.ValidationError(
                    dict.fromkeys(unsupported_fields, message),
                )
        return cast("dict[str, object]", super().to_internal_value(data))

    def validate_gaussian_sigma(self, value: float) -> float:
        if value <= 0:
            message = "Gaussian sigma must be greater than zero."
            raise serializers.ValidationError(message)
        return value

    def validate_window_width(self, value: float) -> float:
        if value <= 0:
            message = "Window width must be greater than zero."
            raise serializers.ValidationError(message)
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        lower_percentile = cast("float", attrs.get("lower_percentile", 1.0))
        upper_percentile = cast("float", attrs.get("upper_percentile", 99.0))
        if not 0 <= lower_percentile < upper_percentile <= MAX_PERCENTILE:
            raise serializers.ValidationError(
                {"percentiles": "Percentiles must satisfy 0 <= lower < upper <= 100."},
            )
        return attrs
