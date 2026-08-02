"""Tests for DB-selected local DICOM pixel loading."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

from apps.analysis.imaging_io import (
    DicomPixelLoadError,
    LoadedDicomPixels,
    load_dicom_pixels_for_series,
    resolve_registered_dicom_path,
    select_instance_for_series,
)
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy, LocalDicomFile

if TYPE_CHECKING:
    from pathlib import Path


class FakeDicomDataset:
    """Small pydicom-like object used to test decoding boundaries without DICOM files."""

    def __init__(
        self,
        *,
        sop_instance_uid: str,
        series_instance_uid: str,
        pixel_array: np.ndarray[Any, Any],
        rows: Any,
        columns: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        self.SOPInstanceUID = sop_instance_uid
        self.SeriesInstanceUID = series_instance_uid
        self.pixel_array = pixel_array
        self.Rows = rows
        self.Columns = columns
        self.RescaleSlope = metadata.get("RescaleSlope", "1.5")
        self.RescaleIntercept = metadata.get("RescaleIntercept", "-1024")
        self.PixelSpacing = metadata.get("PixelSpacing", ("0.976562", "0.976562"))
        self.SliceThickness = metadata.get("SliceThickness", "2.5")
        self.PhotometricInterpretation = "MONOCHROME2"


@pytest.fixture
def repository_root(tmp_path: Path) -> Path:
    (tmp_path / "datasets" / "raw").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def registered_series(repository_root: Path) -> ImagingSeries:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.3680043.8.498.600",
        source_dataset="pixel-loader-test-dataset",
        source_subject_id="pixel-loader-test-subject",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.700",
        modality="CT",
        number_of_instances=3,
    )
    for index in range(3):
        instance = ImagingInstance.objects.create(
            series=series,
            sop_instance_uid=f"1.2.826.0.1.3680043.8.498.80{index}",
            instance_number=index + 1,
            rows=2,
            columns=3,
            file_sha256=f"{index}" * 64,
        )
        relative_path = f"datasets/raw/test-series/file-{index}.dcm"
        file_path = repository_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(f"metadata-only placeholder {index}".encode())
        LocalDicomFile.objects.create(
            instance=instance,
            relative_path=relative_path,
            file_sha256=instance.file_sha256,
            file_size_bytes=file_path.stat().st_size,
            is_available=True,
        )
    return series


@pytest.mark.django_db
def test_select_instance_for_series_uses_middle_available_slice(
    registered_series: ImagingSeries,
) -> None:
    instance, slice_index, instance_count = select_instance_for_series(
        registered_series.series_instance_uid,
    )

    assert slice_index == 1
    assert instance_count == 3
    assert instance.instance_number == 2


@pytest.mark.django_db
def test_select_instance_for_series_uses_explicit_zero_based_index(
    registered_series: ImagingSeries,
) -> None:
    instance, slice_index, instance_count = select_instance_for_series(
        registered_series.series_instance_uid,
        slice_index=2,
    )

    assert slice_index == 2
    assert instance_count == 3
    assert instance.instance_number == 3


@pytest.mark.django_db
def test_select_instance_for_series_rejects_negative_index(
    registered_series: ImagingSeries,
) -> None:
    with pytest.raises(DicomPixelLoadError, match="zero or greater"):
        select_instance_for_series(registered_series.series_instance_uid, slice_index=-1)


@pytest.mark.django_db
def test_select_instance_for_series_rejects_out_of_range_index(
    registered_series: ImagingSeries,
) -> None:
    with pytest.raises(DicomPixelLoadError, match="outside the available range"):
        select_instance_for_series(registered_series.series_instance_uid, slice_index=3)


@pytest.mark.django_db
def test_select_instance_for_series_rejects_missing_series() -> None:
    with pytest.raises(DicomPixelLoadError, match="Imaging series was not found"):
        select_instance_for_series("1.2.826.0.1.3680043.8.498.missing")


@pytest.mark.django_db
def test_select_instance_for_series_rejects_series_with_no_available_local_file() -> None:
    study = ImagingStudy.objects.create(study_instance_uid="1.2.826.0.1.3680043.8.498.900")
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.901",
        modality="PT",
        number_of_instances=1,
    )
    ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.902",
        instance_number=1,
        file_sha256="9" * 64,
    )

    with pytest.raises(DicomPixelLoadError, match="No available local DICOM files"):
        select_instance_for_series(series.series_instance_uid)


def test_resolve_registered_dicom_path_accepts_safe_raw_file(repository_root: Path) -> None:
    relative_path = "datasets/raw/test-series/file.dcm"
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"metadata-only placeholder")

    resolved = resolve_registered_dicom_path(relative_path, repository_root)

    assert resolved == file_path.resolve()


def test_resolve_registered_dicom_path_rejects_absolute_path(repository_root: Path) -> None:
    absolute_path = repository_root / "datasets" / "raw" / "test-series" / "file.dcm"

    with pytest.raises(DicomPixelLoadError, match="repository-relative"):
        resolve_registered_dicom_path(str(absolute_path), repository_root)


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside/file.dcm",
        "datasets/raw/../../outside/file.dcm",
    ],
)
def test_resolve_registered_dicom_path_rejects_parent_traversal(
    repository_root: Path,
    relative_path: str,
) -> None:
    with pytest.raises(DicomPixelLoadError, match="parent traversal"):
        resolve_registered_dicom_path(relative_path, repository_root)


def test_resolve_registered_dicom_path_rejects_path_outside_repository(
    repository_root: Path,
) -> None:
    outside_file = repository_root.parent / f"{repository_root.name}-outside.dcm"
    outside_file.write_bytes(b"outside")
    symlink_path = repository_root / "datasets" / "raw" / "outside-link.dcm"
    symlink_path.symlink_to(outside_file)

    with pytest.raises(DicomPixelLoadError, match="outside the repository"):
        resolve_registered_dicom_path("datasets/raw/outside-link.dcm", repository_root)


def test_resolve_registered_dicom_path_rejects_path_outside_raw_root(
    repository_root: Path,
) -> None:
    relative_path = "not-raw/file.dcm"
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"metadata-only placeholder")

    with pytest.raises(DicomPixelLoadError, match="inside datasets/raw"):
        resolve_registered_dicom_path(relative_path, repository_root)


def test_resolve_registered_dicom_path_rejects_missing_file(repository_root: Path) -> None:
    with pytest.raises(DicomPixelLoadError, match="does not exist"):
        resolve_registered_dicom_path("datasets/raw/missing/file.dcm", repository_root)


def test_resolve_registered_dicom_path_rejects_directory(repository_root: Path) -> None:
    relative_path = "datasets/raw/test-series/directory"
    directory_path = repository_root / relative_path
    directory_path.mkdir(parents=True)

    with pytest.raises(DicomPixelLoadError, match="not a file"):
        resolve_registered_dicom_path(relative_path, repository_root)


@pytest.mark.django_db
def test_load_dicom_pixels_rejects_registry_checksum_mismatch(
    registered_series: ImagingSeries,
    repository_root: Path,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    local_file = selected_instance.local_file
    local_file.file_sha256 = "f" * 64
    local_file.save(update_fields=["file_sha256"])

    with pytest.raises(DicomPixelLoadError, match="checksum"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_rejects_sop_instance_uid_mismatch(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid="1.2.826.0.1.3680043.8.498.bad",
            series_instance_uid=registered_series.series_instance_uid,
            pixel_array=np.arange(6, dtype=np.int16).reshape(2, 3),
            rows=2,
            columns=3,
        ),
    )

    with pytest.raises(DicomPixelLoadError, match="SOPInstanceUID"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_rejects_series_instance_uid_mismatch(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid=selected_instance.sop_instance_uid,
            series_instance_uid="1.2.826.0.1.3680043.8.498.bad",
            pixel_array=np.arange(6, dtype=np.int16).reshape(2, 3),
            rows=2,
            columns=3,
        ),
    )

    with pytest.raises(DicomPixelLoadError, match="SeriesInstanceUID"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_rejects_non_2d_pixel_array(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid=selected_instance.sop_instance_uid,
            series_instance_uid=registered_series.series_instance_uid,
            pixel_array=np.arange(12, dtype=np.int16).reshape(2, 2, 3),
            rows=2,
            columns=3,
        ),
    )

    with pytest.raises(DicomPixelLoadError, match="two-dimensional"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_rejects_rows_columns_mismatch(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid=selected_instance.sop_instance_uid,
            series_instance_uid=registered_series.series_instance_uid,
            pixel_array=np.arange(6, dtype=np.int16).reshape(2, 3),
            rows=3,
            columns=3,
        ),
    )

    with pytest.raises(DicomPixelLoadError, match="Rows/Columns"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_converts_malformed_numeric_metadata_to_loader_error(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid=selected_instance.sop_instance_uid,
            series_instance_uid=registered_series.series_instance_uid,
            pixel_array=np.arange(6, dtype=np.int16).reshape(2, 3),
            rows=2,
            columns=3,
            metadata={"RescaleSlope": "not-a-number"},
        ),
    )

    with pytest.raises(DicomPixelLoadError, match="RescaleSlope"):
        load_dicom_pixels_for_series(
            registered_series.series_instance_uid,
            repo_root=repository_root,
        )


@pytest.mark.django_db
def test_load_dicom_pixels_returns_loaded_metadata(
    registered_series: ImagingSeries,
    repository_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_instance, _, _ = select_instance_for_series(registered_series.series_instance_uid)
    monkeypatch.setattr(
        "apps.analysis.imaging_io.pydicom.dcmread",
        lambda path: FakeDicomDataset(
            sop_instance_uid=selected_instance.sop_instance_uid,
            series_instance_uid=registered_series.series_instance_uid,
            pixel_array=np.arange(6, dtype=np.int16).reshape(2, 3),
            rows=2,
            columns=3,
        ),
    )

    loaded = load_dicom_pixels_for_series(
        registered_series.series_instance_uid,
        repo_root=repository_root,
    )

    assert isinstance(loaded, LoadedDicomPixels)
    assert loaded.study_instance_uid == registered_series.study.study_instance_uid
    assert loaded.series_instance_uid == registered_series.series_instance_uid
    assert loaded.sop_instance_uid == selected_instance.sop_instance_uid
    assert loaded.slice_index == 1
    assert loaded.series_instance_count == 3
    assert loaded.modality == "CT"
    assert loaded.pixel_array.shape == (2, 3)
    assert loaded.rows == 2
    assert loaded.columns == 3
    assert loaded.numpy_dtype == "int16"
    assert loaded.rescale_slope == 1.5
    assert loaded.rescale_intercept == -1024.0
    assert loaded.pixel_spacing == (0.976562, 0.976562)
    assert loaded.slice_thickness == 2.5
    assert loaded.photometric_interpretation == "MONOCHROME2"
