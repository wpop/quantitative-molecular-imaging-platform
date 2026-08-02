"""Tests for private scientific operations on DB-selected DICOM pixels."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter, sobel

from apps.analysis.imaging_io import LoadedDicomPixels
from apps.analysis.scientific_operations import (
    ScientificOperation,
    ScientificOperationError,
    ScientificOperationResult,
    apply_gaussian_filter,
    apply_sobel_gradient_magnitude,
    rescale_dicom_pixels,
    run_scientific_operation_for_series,
)


def loaded_pixels(
    pixel_array: np.ndarray[Any, Any] | None = None,
    *,
    modality: str = "CT",
    rescale_slope: float = 2.0,
    rescale_intercept: float = -10.0,
) -> LoadedDicomPixels:
    pixels = (
        np.array(
            [
                [0, 1, 2],
                [3, 4, 5],
            ],
            dtype=np.int16,
        )
        if pixel_array is None
        else pixel_array
    )
    return LoadedDicomPixels(
        study_instance_uid="1.2.826.0.1.3680043.8.498.100",
        series_instance_uid="1.2.826.0.1.3680043.8.498.200",
        sop_instance_uid="1.2.826.0.1.3680043.8.498.300",
        instance_id=42,
        slice_index=1,
        series_instance_count=3,
        modality=modality,
        relative_path="datasets/raw/not-returned.dcm",
        pixel_array=pixels,
        rows=int(pixels.shape[0]),
        columns=int(pixels.shape[1]),
        numpy_dtype=str(pixels.dtype),
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
        pixel_spacing=(1.0, 1.0),
        slice_thickness=2.5,
        photometric_interpretation="MONOCHROME2",
    )


def patch_loader(monkeypatch: pytest.MonkeyPatch, loaded: LoadedDicomPixels) -> None:
    monkeypatch.setattr(
        "apps.analysis.scientific_operations.load_dicom_pixels_for_series",
        lambda **kwargs: loaded,
    )


def test_scientific_operation_values_are_exact() -> None:
    assert [operation.value for operation in ScientificOperation] == [
        "rescale",
        "gaussian",
        "sobel",
    ]


def test_scientific_operation_result_fields_are_exact_and_frozen() -> None:
    assert cast("Any", ScientificOperationResult).__dataclass_params__.frozen
    assert [field.name for field in fields(ScientificOperationResult)] == [
        "operation",
        "study_instance_uid",
        "series_instance_uid",
        "sop_instance_uid",
        "instance_id",
        "slice_index",
        "series_instance_count",
        "modality",
        "source_dtype",
        "result_dtype",
        "rows",
        "columns",
        "value_units",
        "gaussian_sigma",
        "source_minimum",
        "source_maximum",
        "source_mean",
        "result_minimum",
        "result_maximum",
        "result_mean",
        "result_standard_deviation",
        "result_array",
    ]


def test_rescale_dicom_pixels_applies_ct_hounsfield_units() -> None:
    pixel_array = np.array([[0, 1], [2, 3]], dtype=np.int16)

    rescaled, units = rescale_dicom_pixels(pixel_array, "CT", 1.5, -1024.0)

    assert units == "HU"
    np.testing.assert_allclose(
        rescaled,
        np.array([[-1024.0, -1022.5], [-1021.0, -1019.5]], dtype=np.float32),
    )


def test_rescale_dicom_pixels_pt_rescaling_does_not_claim_suv() -> None:
    rescaled, units = rescale_dicom_pixels(np.array([[1, 2]], dtype=np.uint16), "PT", 2.0, 3.0)

    assert units == "rescaled_pixel_value"
    assert "SUV" not in units.upper()
    np.testing.assert_allclose(rescaled, np.array([[5.0, 7.0]], dtype=np.float32))


def test_rescale_dicom_pixels_returns_float32_for_other_modalities() -> None:
    rescaled, units = rescale_dicom_pixels(np.array([[1, 2]], dtype=np.uint16), "MR", 2.0, 3.0)

    assert units == "rescaled_pixel_value"
    assert rescaled.dtype == np.float32


def test_rescale_dicom_pixels_rejects_non_2d_array() -> None:
    with pytest.raises(ScientificOperationError, match="two-dimensional"):
        rescale_dicom_pixels(np.arange(4, dtype=np.int16), "CT", 1.0, 0.0)


def test_rescale_dicom_pixels_rejects_empty_array() -> None:
    with pytest.raises(ScientificOperationError, match="empty"):
        rescale_dicom_pixels(np.empty((0, 2), dtype=np.int16), "CT", 1.0, 0.0)


def test_rescale_dicom_pixels_rejects_non_finite_slope() -> None:
    with pytest.raises(ScientificOperationError, match="rescale_slope"):
        rescale_dicom_pixels(np.array([[1]], dtype=np.int16), "CT", float("nan"), 0.0)


def test_rescale_dicom_pixels_rejects_non_finite_intercept() -> None:
    with pytest.raises(ScientificOperationError, match="rescale_intercept"):
        rescale_dicom_pixels(np.array([[1]], dtype=np.int16), "CT", 1.0, float("inf"))


def test_rescale_dicom_pixels_rejects_non_finite_source_values() -> None:
    with pytest.raises(ScientificOperationError, match="pixel_array"):
        rescale_dicom_pixels(np.array([[np.nan]], dtype=np.float32), "CT", 1.0, 0.0)


def test_rescale_dicom_pixels_rejects_non_finite_result_values_where_representable() -> None:
    with pytest.raises(ScientificOperationError, match="rescaled pixel array"):
        rescale_dicom_pixels(
            np.array([[np.finfo(np.float32).max]], dtype=np.float32),
            "CT",
            2.0,
            0.0,
        )


def test_apply_gaussian_filter_shape_dtype_and_scipy_result() -> None:
    pixel_array = np.arange(9, dtype=np.float32).reshape(3, 3)

    filtered = apply_gaussian_filter(pixel_array, sigma=1.0)

    assert filtered.shape == pixel_array.shape
    assert filtered.dtype == np.float32
    np.testing.assert_allclose(filtered, gaussian_filter(pixel_array, sigma=1.0))


def test_apply_gaussian_filter_does_not_modify_input() -> None:
    pixel_array = np.arange(9, dtype=np.float32).reshape(3, 3)
    original = pixel_array.copy()

    apply_gaussian_filter(pixel_array, sigma=1.0)

    np.testing.assert_array_equal(pixel_array, original)


def test_apply_gaussian_filter_rejects_sigma_zero() -> None:
    with pytest.raises(ScientificOperationError, match="greater than zero"):
        apply_gaussian_filter(np.ones((2, 2), dtype=np.float32), sigma=0.0)


def test_apply_gaussian_filter_rejects_negative_sigma() -> None:
    with pytest.raises(ScientificOperationError, match="greater than zero"):
        apply_gaussian_filter(np.ones((2, 2), dtype=np.float32), sigma=-1.0)


def test_apply_gaussian_filter_rejects_non_finite_sigma() -> None:
    with pytest.raises(ScientificOperationError, match="sigma"):
        apply_gaussian_filter(np.ones((2, 2), dtype=np.float32), sigma=float("nan"))


def test_apply_gaussian_filter_rejects_non_2d_array() -> None:
    with pytest.raises(ScientificOperationError, match="two-dimensional"):
        apply_gaussian_filter(np.arange(4, dtype=np.float32), sigma=1.0)


def test_apply_gaussian_filter_rejects_empty_array() -> None:
    with pytest.raises(ScientificOperationError, match="empty"):
        apply_gaussian_filter(np.empty((0, 2), dtype=np.float32), sigma=1.0)


def test_apply_gaussian_filter_rejects_non_finite_input() -> None:
    with pytest.raises(ScientificOperationError, match="pixel_array"):
        apply_gaussian_filter(np.array([[np.inf]], dtype=np.float32), sigma=1.0)


def test_apply_sobel_gradient_magnitude_shape_dtype_and_scipy_result() -> None:
    pixel_array = np.arange(9, dtype=np.float32).reshape(3, 3)
    expected = np.hypot(sobel(pixel_array, axis=1), sobel(pixel_array, axis=0))

    magnitude = apply_sobel_gradient_magnitude(pixel_array)

    assert magnitude.shape == pixel_array.shape
    assert magnitude.dtype == np.float32
    np.testing.assert_allclose(magnitude, expected)


def test_apply_sobel_gradient_magnitude_constant_input_is_zero() -> None:
    magnitude = apply_sobel_gradient_magnitude(np.full((3, 3), 7.0, dtype=np.float32))

    np.testing.assert_array_equal(magnitude, np.zeros((3, 3), dtype=np.float32))


def test_apply_sobel_gradient_magnitude_does_not_modify_input() -> None:
    pixel_array = np.arange(9, dtype=np.float32).reshape(3, 3)
    original = pixel_array.copy()

    apply_sobel_gradient_magnitude(pixel_array)

    np.testing.assert_array_equal(pixel_array, original)


def test_apply_sobel_gradient_magnitude_rejects_non_2d_array() -> None:
    with pytest.raises(ScientificOperationError, match="two-dimensional"):
        apply_sobel_gradient_magnitude(np.arange(4, dtype=np.float32))


def test_apply_sobel_gradient_magnitude_rejects_empty_array() -> None:
    with pytest.raises(ScientificOperationError, match="empty"):
        apply_sobel_gradient_magnitude(np.empty((0, 2), dtype=np.float32))


def test_apply_sobel_gradient_magnitude_rejects_non_finite_input() -> None:
    with pytest.raises(ScientificOperationError, match="pixel_array"):
        apply_sobel_gradient_magnitude(np.array([[np.nan]], dtype=np.float32))


def test_run_scientific_operation_for_series_orchestrates_rescale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels()
    repo_root = Path("repository-root")

    def fake_load_dicom_pixels_for_series(
        series_instance_uid: str,
        slice_index: int | None = None,
        repo_root: Path | None = None,
    ) -> LoadedDicomPixels:
        assert series_instance_uid == loaded.series_instance_uid
        assert slice_index == 1
        assert repo_root == Path("repository-root")
        return loaded

    monkeypatch.setattr(
        "apps.analysis.scientific_operations.load_dicom_pixels_for_series",
        fake_load_dicom_pixels_for_series,
    )

    result = run_scientific_operation_for_series(
        loaded.series_instance_uid,
        "rescale",
        slice_index=1,
        repo_root=repo_root,
    )

    assert result.operation is ScientificOperation.RESCALE
    assert result.value_units == "HU"
    assert result.gaussian_sigma is None
    np.testing.assert_allclose(
        result.result_array,
        np.array([[-10, -8, -6], [-4, -2, 0]], dtype=np.float32),
    )


def test_run_scientific_operation_for_series_orchestrates_gaussian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels(rescale_slope=2.0, rescale_intercept=1.0)
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(
        loaded.series_instance_uid,
        ScientificOperation.GAUSSIAN,
        gaussian_sigma=0.5,
    )

    rescaled = loaded.pixel_array.astype(np.float32) * np.float32(2.0) + np.float32(1.0)
    expected = gaussian_filter(rescaled, sigma=0.5)
    assert result.operation is ScientificOperation.GAUSSIAN
    assert result.gaussian_sigma == 0.5
    assert result.value_units == "HU"
    np.testing.assert_allclose(result.result_array, expected)


def test_run_scientific_operation_for_series_orchestrates_sobel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels(rescale_slope=2.0, rescale_intercept=0.0)
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "sobel")

    rescaled = loaded.pixel_array.astype(np.float32) * np.float32(2.0)
    expected = np.hypot(sobel(rescaled, axis=1), sobel(rescaled, axis=0))
    assert result.operation is ScientificOperation.SOBEL
    assert result.gaussian_sigma is None
    np.testing.assert_allclose(result.result_array, expected)


def test_run_scientific_operation_for_series_rejects_unknown_operation() -> None:
    with pytest.raises(ScientificOperationError, match="Unknown scientific operation"):
        run_scientific_operation_for_series("1.2.3", "median")


def test_run_scientific_operation_for_series_returns_loaded_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels()
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "rescale")

    assert result.study_instance_uid == loaded.study_instance_uid
    assert result.series_instance_uid == loaded.series_instance_uid
    assert result.sop_instance_uid == loaded.sop_instance_uid
    assert result.instance_id == loaded.instance_id
    assert result.slice_index == loaded.slice_index
    assert result.series_instance_count == loaded.series_instance_count
    assert result.modality == loaded.modality
    assert result.rows == loaded.rows
    assert result.columns == loaded.columns


def test_run_scientific_operation_for_series_source_statistics_use_raw_pixels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels()
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "rescale")

    assert result.source_dtype == "int16"
    assert result.source_minimum == 0.0
    assert result.source_maximum == 5.0
    assert result.source_mean == 2.5


def test_run_scientific_operation_for_series_result_statistics_use_final_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels()
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "sobel")

    assert result.result_dtype == "float32"
    assert result.result_minimum == float(np.min(result.result_array))
    assert result.result_maximum == float(np.max(result.result_array))
    assert result.result_mean == float(np.mean(result.result_array))
    assert result.result_standard_deviation == float(np.std(result.result_array))


def test_run_scientific_operation_for_series_ct_sobel_units_are_gradient_magnitude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels(modality="CT")
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "sobel")

    assert result.value_units == "HU_gradient_magnitude"


def test_run_scientific_operation_for_series_pt_rescale_units_are_rescaled_pixel_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels(modality="PT")
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "rescale")

    assert result.value_units == "rescaled_pixel_value"
    assert "SUV" not in result.value_units.upper()


def test_run_scientific_operation_for_series_pt_sobel_units_are_gradient_magnitude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels(modality="PT")
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "sobel")

    assert result.value_units == "rescaled_pixel_value_gradient_magnitude"


def test_scientific_operation_result_contains_no_local_or_absolute_path_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = loaded_pixels()
    patch_loader(monkeypatch, loaded)

    result = run_scientific_operation_for_series(loaded.series_instance_uid, "rescale")

    field_names = {field.name for field in fields(result)}
    assert "relative_path" not in field_names
    assert "path" not in field_names
    assert "local_path" not in field_names
