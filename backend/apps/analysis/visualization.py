"""Local PNG visualization artifacts for private scientific DICOM results."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from apps.analysis.scientific_operations import (
    ScientificOperation,
    run_scientific_operation_for_series,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from apps.analysis.scientific_operations import ScientificOperationResult

SUPPORTED_PIXEL_DIMENSIONS = 2
PNG_MIME_TYPE = "image/png"
SERIES_HASH_LENGTH = 12
MAX_PERCENTILE = 100.0


class VisualizationError(RuntimeError):
    """Raised when a local visualization artifact cannot be generated."""


@dataclass(frozen=True)
class VisualizationArtifactResult:
    """Metadata for one generated local PNG artifact."""

    operation: ScientificOperation
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    instance_id: int
    slice_index: int
    modality: str
    value_units: str
    rows: int
    columns: int
    colormap: str
    display_minimum: float
    display_maximum: float
    window_center: float | None
    window_width: float | None
    relative_png_path: str
    mime_type: str
    file_size_bytes: int
    sha256: str


def _require_2d_non_empty_finite_array(pixel_array: NDArray[Any], *, name: str) -> None:
    if pixel_array.ndim != SUPPORTED_PIXEL_DIMENSIONS:
        message = f"{name} must be a two-dimensional array, got {pixel_array.ndim}D."
        raise VisualizationError(message)
    if pixel_array.size == 0:
        message = f"{name} must not be empty."
        raise VisualizationError(message)
    if not np.all(np.isfinite(pixel_array)):
        message = f"{name} contains non-finite values."
        raise VisualizationError(message)


def _require_finite_number(value: float, *, name: str) -> None:
    if not np.isfinite(value):
        message = f"{name} must be finite."
        raise VisualizationError(message)


def _operation_from_value(operation: ScientificOperation | str) -> ScientificOperation:
    if isinstance(operation, ScientificOperation):
        return operation
    try:
        return ScientificOperation(operation)
    except ValueError as exc:
        supported = ", ".join(item.value for item in ScientificOperation)
        message = (
            f"Unknown visualization operation {operation!r}. "
            f"Supported operations: {supported}."
        )
        raise VisualizationError(message) from exc


def apply_ct_window(
    pixel_array: NDArray[Any],
    window_center: float,
    window_width: float,
) -> tuple[NDArray[np.float32], float, float]:
    """Clip CT intensities to an explicit window and return float32 values."""
    _require_2d_non_empty_finite_array(pixel_array, name="pixel_array")
    _require_finite_number(window_center, name="window_center")
    _require_finite_number(window_width, name="window_width")
    if window_width <= 0:
        message = "window_width must be greater than zero."
        raise VisualizationError(message)

    lower = float(window_center - window_width / 2.0)
    upper = float(window_center + window_width / 2.0)
    windowed = np.clip(pixel_array, lower, upper).astype(np.float32, copy=True)
    return windowed, lower, upper


def calculate_percentile_display_range(
    pixel_array: NDArray[Any],
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
) -> tuple[float, float]:
    """Calculate a finite non-zero percentile display range for a 2D array."""
    _require_2d_non_empty_finite_array(pixel_array, name="pixel_array")
    _require_finite_number(lower_percentile, name="lower_percentile")
    _require_finite_number(upper_percentile, name="upper_percentile")
    if not 0 <= lower_percentile < upper_percentile <= MAX_PERCENTILE:
        message = "Percentiles must satisfy 0 <= lower < upper <= 100."
        raise VisualizationError(message)

    display_minimum = float(np.percentile(pixel_array, lower_percentile))
    display_maximum = float(np.percentile(pixel_array, upper_percentile))
    if not np.isfinite(display_minimum) or not np.isfinite(display_maximum):
        message = "Percentile display range must be finite."
        raise VisualizationError(message)
    if display_minimum == display_maximum:
        display_minimum -= 0.5
        display_maximum += 0.5
    if display_minimum >= display_maximum:
        message = "Percentile display range must be non-zero."
        raise VisualizationError(message)
    return display_minimum, display_maximum


def _repo_relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        message = "Visualization artifact path must remain inside the repository."
        raise VisualizationError(message) from exc


def _resolve_output_root(output_root: Path, repo_root: Path) -> Path:
    if output_root.is_absolute():
        resolved_output_root = output_root.resolve()
        _repo_relative_path(resolved_output_root, repo_root)
        return resolved_output_root
    return (repo_root / output_root).resolve()


def _series_directory_name(series_instance_uid: str) -> str:
    return hashlib.sha256(series_instance_uid.encode()).hexdigest()[:SERIES_HASH_LENGTH]


def _artifact_filename(scientific_result: ScientificOperationResult) -> str:
    modality = scientific_result.modality.lower()
    operation = scientific_result.operation.value
    return f"{modality}_{operation}_slice_{scientific_result.slice_index:04d}.png"


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_array_and_range(
    scientific_result: ScientificOperationResult,
    window_center: float | None,
    window_width: float | None,
    lower_percentile: float,
    upper_percentile: float,
) -> tuple[NDArray[np.float32], str, float, float, float | None, float | None]:
    result_array = np.asarray(scientific_result.result_array)
    _require_2d_non_empty_finite_array(result_array, name="result_array")

    modality = scientific_result.modality.upper()
    operation = scientific_result.operation
    ct_intensity_operations = {ScientificOperation.RESCALE, ScientificOperation.GAUSSIAN}
    if modality == "CT" and operation in ct_intensity_operations:
        if window_center is None or window_width is None:
            message = "CT intensity visualization requires explicit window center and width."
            raise VisualizationError(message)
        display_array, display_minimum, display_maximum = apply_ct_window(
            result_array,
            window_center=window_center,
            window_width=window_width,
        )
        return display_array, "gray", display_minimum, display_maximum, window_center, window_width

    if modality == "CT" and operation is ScientificOperation.SOBEL:
        _, upper = calculate_percentile_display_range(
            result_array,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )
        return result_array.astype(np.float32, copy=True), "magma", 0.0, upper, None, None

    if modality == "PT":
        lower, upper = calculate_percentile_display_range(
            result_array,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )
        return result_array.astype(np.float32, copy=True), "inferno", lower, upper, None, None

    lower, upper = calculate_percentile_display_range(
        result_array,
        lower_percentile=lower_percentile,
        upper_percentile=upper_percentile,
    )
    return result_array.astype(np.float32, copy=True), "viridis", lower, upper, None, None


def generate_visualization_artifact(  # noqa: PLR0913
    scientific_result: ScientificOperationResult,
    output_root: Path,
    repo_root: Path,
    window_center: float | None = None,
    window_width: float | None = None,
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
    dpi: int = 150,
) -> VisualizationArtifactResult:
    """Render a scientific operation result as a local PNG artifact."""
    if dpi <= 0:
        message = "dpi must be greater than zero."
        raise VisualizationError(message)

    display_array, colormap, display_minimum, display_maximum, used_center, used_width = (
        _display_array_and_range(
            scientific_result=scientific_result,
            window_center=window_center,
            window_width=window_width,
            lower_percentile=lower_percentile,
            upper_percentile=upper_percentile,
        )
    )
    output_directory = (
        _resolve_output_root(output_root, repo_root)
        / _series_directory_name(scientific_result.series_instance_uid)
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / _artifact_filename(scientific_result)
    relative_path = _repo_relative_path(output_path, repo_root)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=dpi)
    try:
        image = ax.imshow(
            display_array,
            cmap=colormap,
            vmin=display_minimum,
            vmax=display_maximum,
            aspect="equal",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(
            (
                f"{scientific_result.modality} {scientific_result.operation.value} "
                f"slice {scientific_result.slice_index} ({scientific_result.value_units})"
            ),
            fontsize=9,
        )
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label(scientific_result.value_units)
        fig.tight_layout()
        fig.savefig(output_path, format="png", dpi=dpi)
    finally:
        plt.close(fig)

    if not output_path.exists():
        message = "Visualization PNG was not created."
        raise VisualizationError(message)
    file_size = output_path.stat().st_size
    if file_size <= 0:
        message = "Visualization PNG is empty."
        raise VisualizationError(message)

    return VisualizationArtifactResult(
        operation=scientific_result.operation,
        study_instance_uid=scientific_result.study_instance_uid,
        series_instance_uid=scientific_result.series_instance_uid,
        sop_instance_uid=scientific_result.sop_instance_uid,
        instance_id=scientific_result.instance_id,
        slice_index=scientific_result.slice_index,
        modality=scientific_result.modality,
        value_units=scientific_result.value_units,
        rows=scientific_result.rows,
        columns=scientific_result.columns,
        colormap=colormap,
        display_minimum=display_minimum,
        display_maximum=display_maximum,
        window_center=used_center,
        window_width=used_width,
        relative_png_path=relative_path,
        mime_type=PNG_MIME_TYPE,
        file_size_bytes=file_size,
        sha256=_sha256_for_file(output_path),
    )


def run_visualization_for_series(  # noqa: PLR0913
    series_instance_uid: str,
    operation: ScientificOperation | str,
    output_root: Path,
    repo_root: Path,
    slice_index: int | None = None,
    gaussian_sigma: float = 1.0,
    window_center: float | None = None,
    window_width: float | None = None,
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
    dpi: int = 150,
) -> VisualizationArtifactResult:
    """Run a scientific operation and render its result as a local PNG."""
    selected_operation = _operation_from_value(operation)
    scientific_result = run_scientific_operation_for_series(
        series_instance_uid=series_instance_uid,
        operation=selected_operation,
        slice_index=slice_index,
        gaussian_sigma=gaussian_sigma,
        repo_root=repo_root,
    )
    return generate_visualization_artifact(
        scientific_result=scientific_result,
        output_root=output_root,
        repo_root=repo_root,
        window_center=window_center,
        window_width=window_width,
        lower_percentile=lower_percentile,
        upper_percentile=upper_percentile,
        dpi=dpi,
    )
