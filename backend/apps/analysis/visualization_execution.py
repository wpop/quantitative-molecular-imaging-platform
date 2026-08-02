"""Controlled API execution wrapper for visualization artifact generation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.utils import DatabaseError

from apps.analysis.artifact_registry import (
    VisualizationArtifactRegistryError,
    register_visualization_artifact,
)
from apps.analysis.imaging_io import DicomPixelLoadError
from apps.analysis.scientific_operations import ScientificOperationError
from apps.analysis.visualization import VisualizationError, run_visualization_for_series

if TYPE_CHECKING:
    from apps.analysis.models import VisualizationArtifact

DEFAULT_OUTPUT_ROOT = Path("outputs") / "visualizations"


class VisualizationExecutionError(RuntimeError):
    """Raised when an API-triggered visualization cannot be safely completed."""

    def __init__(self, public_message: str, *, series_selection_failed: bool = False) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.series_selection_failed = series_selection_failed


def default_repo_root() -> Path:
    """Return the repository root used for local visualization artifacts."""
    return Path(__file__).resolve().parents[3]


def execute_visualization_request(  # noqa: PLR0913
    *,
    series_instance_uid: str,
    operation: str,
    slice_index: int | None = None,
    gaussian_sigma: float = 1.0,
    window_center: float | None = None,
    window_width: float | None = None,
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
    dpi: int = 150,
) -> VisualizationArtifact:
    """Run the existing visualization pipeline and register the generated artifact."""
    repo_root = default_repo_root()
    try:
        artifact_result = run_visualization_for_series(
            series_instance_uid=series_instance_uid,
            operation=operation,
            output_root=DEFAULT_OUTPUT_ROOT,
            repo_root=repo_root,
            slice_index=slice_index,
            gaussian_sigma=gaussian_sigma,
            window_center=window_center,
            window_width=window_width,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
            dpi=dpi,
        )
        return register_visualization_artifact(artifact_result)
    except DicomPixelLoadError as exc:
        message = "Requested imaging series could not be selected."
        raise VisualizationExecutionError(message, series_selection_failed=True) from exc
    except (
        VisualizationArtifactRegistryError,
        VisualizationError,
        ScientificOperationError,
        ValidationError,
        DatabaseError,
        ImproperlyConfigured,
        OSError,
    ) as exc:
        message = "Visualization artifact could not be generated."
        raise VisualizationExecutionError(message) from exc
