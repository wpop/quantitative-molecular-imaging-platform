"""Tests for local PNG visualization artifacts."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from apps.analysis.scientific_operations import ScientificOperation, ScientificOperationResult
from apps.analysis.visualization import (
    VisualizationError,
    apply_ct_window,
    calculate_percentile_display_range,
    generate_visualization_artifact,
    run_visualization_for_series,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def scientific_result(
    *,
    operation: ScientificOperation = ScientificOperation.RESCALE,
    modality: str = "CT",
    value_units: str = "HU",
    result_array: np.ndarray | None = None,
) -> ScientificOperationResult:
    array = (
        np.array(
            [
                [-1000.0, -500.0, 0.0],
                [100.0, 500.0, 1000.0],
            ],
            dtype=np.float32,
        )
        if result_array is None
        else result_array
    )
    return ScientificOperationResult(
        operation=operation,
        study_instance_uid="1.2.826.0.1.study",
        series_instance_uid="1.2.826.0.1.series",
        sop_instance_uid="1.2.826.0.1.sop",
        instance_id=17,
        slice_index=49,
        series_instance_count=100,
        modality=modality,
        source_dtype="int16",
        result_dtype=str(array.dtype),
        rows=int(array.shape[0]),
        columns=int(array.shape[1]),
        value_units=value_units,
        gaussian_sigma=None,
        source_minimum=float(np.min(array)),
        source_maximum=float(np.max(array)),
        source_mean=float(np.mean(array)),
        result_minimum=float(np.min(array)),
        result_maximum=float(np.max(array)),
        result_mean=float(np.mean(array)),
        result_standard_deviation=float(np.std(array)),
        result_array=array,
    )


def test_apply_ct_window_clips_returns_limits_float32_and_preserves_input() -> None:
    pixel_array = np.array([[-200.0, 0.0, 200.0]], dtype=np.float32)
    original = pixel_array.copy()

    windowed, lower, upper = apply_ct_window(pixel_array, window_center=0.0, window_width=200.0)

    assert lower == -100.0
    assert upper == 100.0
    assert windowed.dtype == np.float32
    np.testing.assert_array_equal(windowed, np.array([[-100.0, 0.0, 100.0]], dtype=np.float32))
    np.testing.assert_array_equal(pixel_array, original)


@pytest.mark.parametrize(
    ("window_center", "window_width", "message"),
    [
        (float("nan"), 100.0, "window_center"),
        (0.0, float("inf"), "window_width"),
        (0.0, 0.0, "greater than zero"),
    ],
)
def test_apply_ct_window_rejects_invalid_window(
    window_center: float,
    window_width: float,
    message: str,
) -> None:
    with pytest.raises(VisualizationError, match=message):
        apply_ct_window(np.ones((2, 2), dtype=np.float32), window_center, window_width)


def test_calculate_percentile_display_range_uses_percentiles_and_preserves_input() -> None:
    pixel_array = np.arange(100, dtype=np.float32).reshape(10, 10)
    original = pixel_array.copy()

    lower, upper = calculate_percentile_display_range(pixel_array, 10.0, 90.0)

    assert lower == float(np.percentile(pixel_array, 10.0))
    assert upper == float(np.percentile(pixel_array, 90.0))
    assert lower < upper
    np.testing.assert_array_equal(pixel_array, original)


@pytest.mark.parametrize(
    ("lower_percentile", "upper_percentile"),
    [
        (-1.0, 99.0),
        (50.0, 50.0),
        (99.0, 101.0),
    ],
)
def test_calculate_percentile_display_range_rejects_invalid_percentiles(
    lower_percentile: float,
    upper_percentile: float,
) -> None:
    with pytest.raises(VisualizationError, match="Percentiles"):
        calculate_percentile_display_range(
            np.ones((2, 2), dtype=np.float32),
            lower_percentile,
            upper_percentile,
        )


def test_calculate_percentile_display_range_expands_equal_values() -> None:
    lower, upper = calculate_percentile_display_range(np.full((2, 2), 7.0, dtype=np.float32))

    assert lower < 7.0 < upper
    assert upper - lower > 0.0


def test_ct_intensity_uses_gray_and_requires_window(tmp_path: Path) -> None:
    result = scientific_result(operation=ScientificOperation.RESCALE)

    with pytest.raises(VisualizationError, match="requires explicit window"):
        generate_visualization_artifact(result, tmp_path / "outputs", tmp_path)

    artifact = generate_visualization_artifact(
        result,
        tmp_path / "outputs",
        tmp_path,
        window_center=0.0,
        window_width=400.0,
    )
    assert artifact.colormap == "gray"
    assert artifact.display_minimum == -200.0
    assert artifact.display_maximum == 200.0


def test_ct_gaussian_requires_window_parameters(tmp_path: Path) -> None:
    result = scientific_result(operation=ScientificOperation.GAUSSIAN)

    with pytest.raises(VisualizationError, match="requires explicit window"):
        generate_visualization_artifact(result, tmp_path / "outputs", tmp_path)


def test_ct_sobel_uses_magma_and_nonnegative_display_minimum(tmp_path: Path) -> None:
    result = scientific_result(
        operation=ScientificOperation.SOBEL,
        value_units="HU_gradient_magnitude",
        result_array=np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32),
    )

    artifact = generate_visualization_artifact(result, tmp_path / "outputs", tmp_path)

    assert artifact.colormap == "magma"
    assert artifact.display_minimum == 0.0
    assert artifact.display_maximum > 0.0


def test_pt_uses_inferno_and_never_suv(tmp_path: Path) -> None:
    result = scientific_result(
        modality="PT",
        value_units="rescaled_pixel_value",
        result_array=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
    )

    artifact = generate_visualization_artifact(result, tmp_path / "outputs", tmp_path)

    assert artifact.colormap == "inferno"
    assert "SUV" not in artifact.value_units.upper()


def test_other_modality_uses_viridis(tmp_path: Path) -> None:
    result = scientific_result(
        modality="MR",
        value_units="rescaled_pixel_value",
        result_array=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
    )

    artifact = generate_visualization_artifact(result, tmp_path / "outputs", tmp_path)

    assert artifact.colormap == "viridis"


def test_png_created_with_valid_signature_relative_path_sha256_and_size(tmp_path: Path) -> None:
    result = scientific_result()

    artifact = generate_visualization_artifact(
        result,
        tmp_path / "outputs",
        tmp_path,
        window_center=0.0,
        window_width=400.0,
    )

    artifact_path = tmp_path / artifact.relative_png_path
    assert artifact_path.exists()
    assert artifact_path.read_bytes().startswith(PNG_SIGNATURE)
    assert not Path(artifact.relative_png_path).is_absolute()
    assert re.fullmatch(r"[0-9a-f]{64}", artifact.sha256)
    assert artifact.file_size_bytes == artifact_path.stat().st_size


def test_visualization_result_contains_no_array_or_absolute_path(tmp_path: Path) -> None:
    result = scientific_result()

    artifact = generate_visualization_artifact(
        result,
        tmp_path / "outputs",
        tmp_path,
        window_center=0.0,
        window_width=400.0,
    )

    assert not hasattr(artifact, "result_array")
    assert not hasattr(artifact, "absolute_path")
    assert not Path(artifact.relative_png_path).is_absolute()


def test_run_visualization_for_series_forwards_operation_slice_and_gaussian_sigma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    result = scientific_result(operation=ScientificOperation.GAUSSIAN)

    def fake_run_scientific_operation_for_series(**kwargs: object) -> ScientificOperationResult:
        calls.update(kwargs)
        return result

    monkeypatch.setattr(
        "apps.analysis.visualization.run_scientific_operation_for_series",
        fake_run_scientific_operation_for_series,
    )

    artifact = run_visualization_for_series(
        series_instance_uid="1.2.series",
        operation="gaussian",
        output_root=tmp_path / "outputs",
        repo_root=tmp_path,
        slice_index=7,
        gaussian_sigma=1.5,
        window_center=0.0,
        window_width=400.0,
    )

    assert calls["operation"] is ScientificOperation.GAUSSIAN
    assert calls["slice_index"] == 7
    assert calls["gaussian_sigma"] == 1.5
    assert artifact.operation is ScientificOperation.GAUSSIAN
