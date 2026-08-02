"""Domain models for quantitative analysis tracking."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models


class AnalysisRun(models.Model):
    """Track one reproducible analysis execution for a study."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    study = models.ForeignKey(
        "imaging.ImagingStudy",
        related_name="analysis_runs",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    name = models.CharField(max_length=255)
    algorithm_name = models.CharField(max_length=255)
    algorithm_version = models.CharField(max_length=64)
    parameters = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "name")
        indexes = (
            models.Index(fields=["study", "status"], name="analysis_run_study_status_idx"),
            models.Index(fields=["algorithm_name"], name="analysis_run_algorithm_idx"),
            models.Index(fields=["created_at"], name="analysis_run_created_idx"),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.algorithm_name} {self.algorithm_version})"


class MeasurementResult(models.Model):
    """Store a quantitative measurement result produced by an analysis run."""

    analysis_run = models.ForeignKey(
        AnalysisRun,
        related_name="measurements",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=20, decimal_places=8)
    unit = models.CharField(max_length=64)
    region_label = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("analysis_run_id", "name", "region_label")
        indexes = (
            models.Index(fields=["analysis_run", "name"], name="measurement_run_name_idx"),
            models.Index(fields=["region_label"], name="measurement_region_idx"),
            models.Index(fields=["created_at"], name="measurement_created_idx"),
        )

    def __str__(self) -> str:
        region = f" [{self.region_label}]" if self.region_label else ""
        return f"{self.name}{region}: {self.value} {self.unit}"


class VisualizationArtifact(models.Model):
    """Store metadata for one local scientific visualization PNG artifact."""

    class Operation(models.TextChoices):
        RESCALE = "rescale", "Rescale"
        GAUSSIAN = "gaussian", "Gaussian"
        SOBEL = "sobel", "Sobel"

    instance = models.ForeignKey(
        "imaging.ImagingInstance",
        related_name="visualization_artifacts",
        on_delete=models.CASCADE,
    )
    operation = models.CharField(max_length=16, choices=Operation.choices)
    modality = models.CharField(max_length=16)
    slice_index = models.PositiveIntegerField()
    value_units = models.CharField(max_length=64)
    relative_path = models.CharField(max_length=512, unique=True)
    mime_type = models.CharField(max_length=64, default="image/png")
    file_size_bytes = models.PositiveBigIntegerField()
    file_sha256 = models.CharField(max_length=64, db_index=True)
    rows = models.PositiveIntegerField()
    columns = models.PositiveIntegerField()
    colormap = models.CharField(max_length=64)
    display_minimum = models.FloatField()
    display_maximum = models.FloatField()
    window_center = models.FloatField(blank=True, null=True)
    window_width = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "relative_path")
        indexes = (
            models.Index(fields=["operation"], name="vis_artifact_operation_idx"),
            models.Index(fields=["modality"], name="vis_artifact_modality_idx"),
            models.Index(fields=["created_at"], name="vis_artifact_created_idx"),
        )

    def __str__(self) -> str:
        return (
            f"{self.modality} {self.operation} visualization "
            f"for {self.instance.sop_instance_uid} slice {self.slice_index}"
        )

    def clean(self) -> None:
        super().clean()
        relative_path = Path(self.relative_path)
        if relative_path.is_absolute():
            raise ValidationError(
                {"relative_path": "Visualization artifact paths must be relative."},
            )
        if ".." in relative_path.parts:
            raise ValidationError(
                {
                    "relative_path": (
                        "Visualization artifact paths must not contain parent traversal."
                    ),
                },
            )
        if not self.relative_path.startswith("outputs/visualizations/"):
            raise ValidationError(
                {
                    "relative_path": (
                        "Visualization artifact paths must begin with "
                        "outputs/visualizations/."
                    ),
                },
            )
