"""Private NumPy/SciPy operations for DB-selected DICOM pixels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from scipy.ndimage import gaussian_filter, sobel

from apps.analysis.imaging_io import load_dicom_pixels_for_series

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray

SUPPORTED_PIXEL_DIMENSIONS = 2


class ScientificOperationError(RuntimeError):
    """Raised when a scientific pixel operation cannot be completed."""


class ScientificOperation(StrEnum):
    """Supported private scientific operations for one selected DICOM slice."""

    RESCALE = "rescale"
    GAUSSIAN = "gaussian"
    SOBEL = "sobel"


@dataclass(frozen=True)
class ScientificOperationResult:
    """Numerical result and provenance for one DB-selected DICOM slice."""

    operation: ScientificOperation
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    instance_id: int
    slice_index: int
    series_instance_count: int
    modality: str
    source_dtype: str
    result_dtype: str
    rows: int
    columns: int
    value_units: str
    gaussian_sigma: float | None
    source_minimum: float
    source_maximum: float
    source_mean: float
    result_minimum: float
    result_maximum: float
    result_mean: float
    result_standard_deviation: float
    result_array: NDArray[Any]


def _require_2d_non_empty_array(pixel_array: NDArray[Any], *, name: str) -> None:
    if pixel_array.ndim != SUPPORTED_PIXEL_DIMENSIONS:
        message = f"{name} must be a two-dimensional array, got {pixel_array.ndim}D."
        raise ScientificOperationError(message)
    if pixel_array.size == 0:
        message = f"{name} must not be empty."
        raise ScientificOperationError(message)


def _require_finite_number(value: float, *, name: str) -> None:
    if not np.isfinite(value):
        message = f"{name} must be finite."
        raise ScientificOperationError(message)


def _require_finite_array(pixel_array: NDArray[Any], *, name: str) -> None:
    if not np.all(np.isfinite(pixel_array)):
        message = f"{name} contains non-finite values."
        raise ScientificOperationError(message)


def _operation_from_value(operation: ScientificOperation | str) -> ScientificOperation:
    if isinstance(operation, ScientificOperation):
        return operation
    try:
        return ScientificOperation(operation)
    except ValueError as exc:
        supported = ", ".join(item.value for item in ScientificOperation)
        message = f"Unknown scientific operation {operation!r}. Supported operations: {supported}."
        raise ScientificOperationError(message) from exc


def rescale_dicom_pixels(
    pixel_array: NDArray[Any],
    modality: str,
    rescale_slope: float,
    rescale_intercept: float,
) -> tuple[NDArray[np.float32], str]:
    """Apply DICOM rescale slope/intercept and return float32 values with units."""
    _require_2d_non_empty_array(pixel_array, name="pixel_array")
    _require_finite_array(pixel_array, name="pixel_array")
    _require_finite_number(rescale_slope, name="rescale_slope")
    _require_finite_number(rescale_intercept, name="rescale_intercept")

    with np.errstate(over="ignore", invalid="ignore"):
        rescaled = (
            np.asarray(pixel_array, dtype=np.float32) * np.float32(rescale_slope)
            + np.float32(rescale_intercept)
        ).astype(np.float32, copy=False)
    _require_finite_array(rescaled, name="rescaled pixel array")

    normalized_modality = modality.upper()
    value_units = "HU" if normalized_modality == "CT" else "rescaled_pixel_value"
    return rescaled, value_units


def apply_gaussian_filter(
    pixel_array: NDArray[np.float32],
    sigma: float,
) -> NDArray[np.float32]:
    """Apply a SciPy Gaussian filter to a two-dimensional float32 array."""
    _require_2d_non_empty_array(pixel_array, name="pixel_array")
    _require_finite_array(pixel_array, name="pixel_array")
    _require_finite_number(sigma, name="sigma")
    if sigma <= 0:
        message = "sigma must be greater than zero."
        raise ScientificOperationError(message)

    filtered = cast(
        "NDArray[np.float32]",
        gaussian_filter(pixel_array, sigma=sigma).astype(np.float32, copy=False),
    )
    _require_finite_array(filtered, name="Gaussian filter output")
    return filtered


def apply_sobel_gradient_magnitude(
    pixel_array: NDArray[np.float32],
) -> NDArray[np.float32]:
    """Compute unnormalized Sobel gradient magnitude for a two-dimensional array."""
    _require_2d_non_empty_array(pixel_array, name="pixel_array")
    _require_finite_array(pixel_array, name="pixel_array")

    gradient_x = sobel(pixel_array, axis=1)
    gradient_y = sobel(pixel_array, axis=0)
    magnitude = cast(
        "NDArray[np.float32]",
        np.hypot(gradient_x, gradient_y).astype(np.float32, copy=False),
    )
    _require_finite_array(magnitude, name="Sobel gradient magnitude output")
    return magnitude


def run_scientific_operation_for_series(
    series_instance_uid: str,
    operation: ScientificOperation | str,
    slice_index: int | None = None,
    gaussian_sigma: float = 1.0,
    repo_root: Path | None = None,
) -> ScientificOperationResult:
    """Run one private scientific operation on real pixels selected through PostgreSQL."""
    selected_operation = _operation_from_value(operation)
    loaded = load_dicom_pixels_for_series(
        series_instance_uid=series_instance_uid,
        slice_index=slice_index,
        repo_root=repo_root,
    )

    rescaled, value_units = rescale_dicom_pixels(
        pixel_array=loaded.pixel_array,
        modality=loaded.modality,
        rescale_slope=loaded.rescale_slope,
        rescale_intercept=loaded.rescale_intercept,
    )

    if selected_operation is ScientificOperation.RESCALE:
        result_array = rescaled
        result_sigma = None
    elif selected_operation is ScientificOperation.GAUSSIAN:
        result_array = apply_gaussian_filter(rescaled, sigma=gaussian_sigma)
        result_sigma = gaussian_sigma
    else:
        result_array = apply_sobel_gradient_magnitude(rescaled)
        result_sigma = None
        value_units = (
            "HU_gradient_magnitude"
            if loaded.modality.upper() == "CT"
            else "rescaled_pixel_value_gradient_magnitude"
        )

    source_array = loaded.pixel_array
    return ScientificOperationResult(
        operation=selected_operation,
        study_instance_uid=loaded.study_instance_uid,
        series_instance_uid=loaded.series_instance_uid,
        sop_instance_uid=loaded.sop_instance_uid,
        instance_id=loaded.instance_id,
        slice_index=loaded.slice_index,
        series_instance_count=loaded.series_instance_count,
        modality=loaded.modality,
        source_dtype=loaded.numpy_dtype,
        result_dtype=str(result_array.dtype),
        rows=loaded.rows,
        columns=loaded.columns,
        value_units=value_units,
        gaussian_sigma=result_sigma,
        source_minimum=float(np.min(source_array)),
        source_maximum=float(np.max(source_array)),
        source_mean=float(np.mean(source_array)),
        result_minimum=float(np.min(result_array)),
        result_maximum=float(np.max(result_array)),
        result_mean=float(np.mean(result_array)),
        result_standard_deviation=float(np.std(result_array)),
        result_array=result_array,
    )
