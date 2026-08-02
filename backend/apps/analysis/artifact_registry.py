"""Register generated visualization artifact metadata in PostgreSQL."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.analysis.models import VisualizationArtifact
from apps.imaging.models import ImagingInstance

if TYPE_CHECKING:
    from apps.analysis.visualization import VisualizationArtifactResult


class VisualizationArtifactRegistryError(RuntimeError):
    """Raised when visualization artifact metadata cannot be registered."""


def _validate_identifiers(
    artifact_result: VisualizationArtifactResult,
    instance: ImagingInstance,
) -> None:
    if artifact_result.sop_instance_uid != instance.sop_instance_uid:
        message = "Artifact SOPInstanceUID does not match the imaging instance."
        raise VisualizationArtifactRegistryError(message)
    if artifact_result.series_instance_uid != instance.series.series_instance_uid:
        message = "Artifact SeriesInstanceUID does not match the imaging series."
        raise VisualizationArtifactRegistryError(message)
    if artifact_result.study_instance_uid != instance.series.study.study_instance_uid:
        message = "Artifact StudyInstanceUID does not match the imaging study."
        raise VisualizationArtifactRegistryError(message)


def _artifact_defaults(
    artifact_result: VisualizationArtifactResult,
    instance: ImagingInstance,
) -> dict[str, Any]:
    return {
        "instance": instance,
        "operation": artifact_result.operation.value,
        "modality": artifact_result.modality,
        "slice_index": artifact_result.slice_index,
        "value_units": artifact_result.value_units,
        "mime_type": artifact_result.mime_type,
        "file_size_bytes": artifact_result.file_size_bytes,
        "file_sha256": artifact_result.sha256,
        "rows": artifact_result.rows,
        "columns": artifact_result.columns,
        "colormap": artifact_result.colormap,
        "display_minimum": artifact_result.display_minimum,
        "display_maximum": artifact_result.display_maximum,
        "window_center": artifact_result.window_center,
        "window_width": artifact_result.window_width,
    }


def register_visualization_artifact(
    artifact_result: VisualizationArtifactResult,
) -> VisualizationArtifact:
    """Create or update a visualization artifact metadata row."""
    try:
        instance = ImagingInstance.objects.select_related("series", "series__study").get(
            id=artifact_result.instance_id,
        )
    except ImagingInstance.DoesNotExist as exc:
        message = f"Imaging instance was not found: {artifact_result.instance_id}"
        raise VisualizationArtifactRegistryError(message) from exc

    _validate_identifiers(artifact_result, instance)
    defaults = _artifact_defaults(artifact_result, instance)
    candidate = VisualizationArtifact(
        relative_path=artifact_result.relative_png_path,
        **defaults,
    )
    candidate.full_clean(validate_unique=False)

    artifact, _ = VisualizationArtifact.objects.update_or_create(
        relative_path=artifact_result.relative_png_path,
        defaults=defaults,
    )
    artifact.full_clean()
    artifact.save()
    return artifact
