"""Local DICOM pixel loading selected through PostgreSQL metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pydicom

from apps.imaging.models import ImagingInstance, ImagingSeries

if TYPE_CHECKING:
    from numpy.typing import NDArray

PIXEL_SPACING_COMPONENTS = 2
SUPPORTED_PIXEL_DIMENSIONS = 2
CONVERSION_ERRORS = (TypeError, ValueError, OverflowError)


class DicomPixelLoadError(RuntimeError):
    """Raised when a DB-selected local DICOM pixel load cannot be completed."""


@dataclass(frozen=True)
class LoadedDicomPixels:
    """Pixels and metadata for one DICOM instance selected by PostgreSQL."""

    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    instance_id: int
    slice_index: int
    series_instance_count: int
    modality: str
    relative_path: str
    pixel_array: NDArray[Any]
    rows: int
    columns: int
    numpy_dtype: str
    rescale_slope: float
    rescale_intercept: float
    pixel_spacing: tuple[float, float] | None
    slice_thickness: float | None
    photometric_interpretation: str | None


def default_repo_root() -> Path:
    """Return the repository root for local scripts and tests."""
    return Path(__file__).resolve().parents[3]


def select_instance_for_series(
    series_instance_uid: str,
    slice_index: int | None = None,
) -> tuple[ImagingInstance, int, int]:
    """Select one available instance from a series using PostgreSQL records only."""
    try:
        series = ImagingSeries.objects.get(series_instance_uid=series_instance_uid)
    except ImagingSeries.DoesNotExist as exc:
        message = f"Imaging series was not found: {series_instance_uid}"
        raise DicomPixelLoadError(message) from exc

    instances = list(
        ImagingInstance.objects.select_related("series", "series__study", "local_file")
        .filter(series=series, local_file__is_available=True)
        .order_by("instance_number", "sop_instance_uid"),
    )
    instance_count = len(instances)
    if instance_count == 0:
        message = f"No available local DICOM files are registered for series: {series_instance_uid}"
        raise DicomPixelLoadError(message)

    selected_index = instance_count // 2 if slice_index is None else slice_index
    if selected_index < 0:
        message = "Slice index must be zero or greater."
        raise DicomPixelLoadError(message)
    if selected_index >= instance_count:
        message = (
            f"Slice index {selected_index} is outside the available range "
            f"0..{instance_count - 1}."
        )
        raise DicomPixelLoadError(message)

    return instances[selected_index], selected_index, instance_count


def resolve_registered_dicom_path(relative_path: str, repo_root: Path) -> Path:
    """Resolve a registered local DICOM path without trusting database contents."""
    registered_path = Path(relative_path)
    if registered_path.is_absolute():
        message = "Registered DICOM path must be repository-relative."
        raise DicomPixelLoadError(message)
    if ".." in registered_path.parts:
        message = "Registered DICOM path must not contain parent traversal."
        raise DicomPixelLoadError(message)

    resolved_repo_root = repo_root.resolve()
    resolved_path = (resolved_repo_root / registered_path).resolve()
    if not resolved_path.is_relative_to(resolved_repo_root):
        message = "Registered DICOM path resolves outside the repository."
        raise DicomPixelLoadError(message)

    raw_root = (resolved_repo_root / "datasets" / "raw").resolve()
    if not resolved_path.is_relative_to(raw_root):
        message = "Registered DICOM path must remain inside datasets/raw."
        raise DicomPixelLoadError(message)

    if not resolved_path.exists():
        message = f"Registered DICOM file does not exist: {registered_path.as_posix()}"
        raise DicomPixelLoadError(message)
    if not resolved_path.is_file():
        message = f"Registered DICOM path is not a file: {registered_path.as_posix()}"
        raise DicomPixelLoadError(message)

    return resolved_path


def float_attribute(dataset: Any, name: str, default: float) -> float:
    value = getattr(dataset, name, default)
    if value in (None, ""):
        return default
    try:
        return float(cast("Any", value))
    except CONVERSION_ERRORS as exc:
        message = f"Invalid numeric DICOM attribute {name}: {value!r}"
        raise DicomPixelLoadError(message) from exc


def optional_float_attribute(dataset: Any, name: str) -> float | None:
    value = getattr(dataset, name, None)
    if value in (None, ""):
        return None
    try:
        return float(cast("Any", value))
    except CONVERSION_ERRORS as exc:
        message = f"Invalid numeric DICOM attribute {name}: {value!r}"
        raise DicomPixelLoadError(message) from exc


def int_attribute(dataset: Any, name: str, default: int) -> int:
    value = getattr(dataset, name, default)
    if value in (None, ""):
        return default
    try:
        return int(cast("Any", value))
    except CONVERSION_ERRORS as exc:
        message = f"Invalid integer DICOM attribute {name}: {value!r}"
        raise DicomPixelLoadError(message) from exc


def pixel_spacing_from_dataset(dataset: Any) -> tuple[float, float] | None:
    value = getattr(dataset, "PixelSpacing", None)
    try:
        if value is None or len(value) < PIXEL_SPACING_COMPONENTS:
            return None
        return (float(value[0]), float(value[1]))
    except CONVERSION_ERRORS as exc:
        message = f"Malformed DICOM attribute PixelSpacing: {value!r}"
        raise DicomPixelLoadError(message) from exc
    except IndexError:
        return None


def load_dicom_pixels_for_series(
    series_instance_uid: str,
    slice_index: int | None = None,
    repo_root: Path | None = None,
) -> LoadedDicomPixels:
    """Load one two-dimensional raw pixel array selected through PostgreSQL."""
    instance, selected_index, instance_count = select_instance_for_series(
        series_instance_uid=series_instance_uid,
        slice_index=slice_index,
    )
    local_file = instance.local_file
    if local_file.file_sha256 != instance.file_sha256:
        message = "Local DICOM file checksum does not match the imaging instance registry."
        raise DicomPixelLoadError(message)

    path = resolve_registered_dicom_path(
        relative_path=local_file.relative_path,
        repo_root=repo_root or default_repo_root(),
    )

    try:
        dataset = pydicom.dcmread(path)
        pixel_array = np.asarray(dataset.pixel_array)
    except Exception as exc:
        message = (
            "Failed to read DICOM pixels from registered local file: "
            f"{local_file.relative_path}"
        )
        raise DicomPixelLoadError(message) from exc

    if pixel_array.ndim != SUPPORTED_PIXEL_DIMENSIONS:
        message = (
            "Only two-dimensional single-frame arrays are supported, "
            f"got {pixel_array.ndim}D."
        )
        raise DicomPixelLoadError(message)

    dicom_sop_instance_uid = str(getattr(dataset, "SOPInstanceUID", ""))
    if dicom_sop_instance_uid != instance.sop_instance_uid:
        message = "DICOM SOPInstanceUID does not match the PostgreSQL imaging instance."
        raise DicomPixelLoadError(message)

    dicom_series_instance_uid = str(getattr(dataset, "SeriesInstanceUID", ""))
    if dicom_series_instance_uid != instance.series.series_instance_uid:
        message = "DICOM SeriesInstanceUID does not match the PostgreSQL imaging series."
        raise DicomPixelLoadError(message)

    rows = int_attribute(dataset, "Rows", int(pixel_array.shape[0]))
    columns = int_attribute(dataset, "Columns", int(pixel_array.shape[1]))
    if pixel_array.shape != (rows, columns):
        message = (
            f"DICOM pixel shape {pixel_array.shape} does not match Rows/Columns "
            f"({rows}, {columns})."
        )
        raise DicomPixelLoadError(message)

    photometric_interpretation = getattr(dataset, "PhotometricInterpretation", None)

    return LoadedDicomPixels(
        study_instance_uid=instance.series.study.study_instance_uid,
        series_instance_uid=instance.series.series_instance_uid,
        sop_instance_uid=instance.sop_instance_uid,
        instance_id=instance.id,
        slice_index=selected_index,
        series_instance_count=instance_count,
        modality=instance.series.modality,
        relative_path=local_file.relative_path,
        pixel_array=pixel_array,
        rows=rows,
        columns=columns,
        numpy_dtype=str(pixel_array.dtype),
        rescale_slope=float_attribute(dataset, "RescaleSlope", 1.0),
        rescale_intercept=float_attribute(dataset, "RescaleIntercept", 0.0),
        pixel_spacing=pixel_spacing_from_dataset(dataset),
        slice_thickness=optional_float_attribute(dataset, "SliceThickness"),
        photometric_interpretation=str(photometric_interpretation)
        if photometric_interpretation is not None
        else None,
    )
