"""Tests for metadata-only series geometry summaries."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.analysis.models import AnalysisRun, MeasurementResult
from apps.analysis.services import compute_series_geometry, run_series_geometry_summary
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy


@pytest.fixture
def geometry_series() -> ImagingSeries:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.3680043.8.498.10",
        source_dataset="unit-test-dataset",
        source_subject_id="unit-test-subject",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.20",
        modality="CT",
        pixel_spacing=[0.5, 0.25],
        slice_thickness=Decimal("2.500"),
        number_of_instances=2,
    )
    ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.30",
        instance_number=1,
        rows=100,
        columns=200,
        file_sha256="1" * 64,
    )
    ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.31",
        instance_number=2,
        rows=100,
        columns=200,
        file_sha256="2" * 64,
    )
    return series


@pytest.mark.django_db
def test_compute_series_geometry_from_metadata(geometry_series: ImagingSeries) -> None:
    summary = compute_series_geometry(geometry_series)

    assert summary.rows == 100
    assert summary.columns == 200
    assert summary.pixel_spacing == [0.5, 0.25]
    assert summary.slice_thickness == Decimal("2.500")
    assert summary.approximate_in_plane_width_mm == Decimal("50.00000000")
    assert summary.approximate_in_plane_height_mm == Decimal("50.00000000")


@pytest.mark.django_db
def test_run_series_geometry_summary_creates_analysis_results(
    geometry_series: ImagingSeries,
) -> None:
    summary = run_series_geometry_summary()

    assert summary.series_analyzed == 1
    assert summary.measurement_results_created == 8
    assert AnalysisRun.objects.count() == 1
    assert MeasurementResult.objects.count() == 8

    width = MeasurementResult.objects.get(name="approximate_in_plane_width")
    height = MeasurementResult.objects.get(name="approximate_in_plane_height")
    assert width.value == Decimal("50.00000000")
    assert width.unit == "mm"
    assert height.value == Decimal("50.00000000")
    assert height.unit == "mm"
