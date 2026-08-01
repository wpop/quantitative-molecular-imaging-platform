"""Tests for local demo pipeline summary helpers."""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from django.utils import timezone

from apps.analysis.models import AnalysisRun, MeasurementResult
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy
from apps.ingestion.models import IngestionJob

if TYPE_CHECKING:
    from collections.abc import Callable


def load_get_database_summary() -> Callable[[], Any]:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "run_local_demo_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_local_demo_pipeline", script_path)
    if spec is None or spec.loader is None:
        message = f"Unable to load local demo pipeline script: {script_path}"
        raise RuntimeError(message)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast("Callable[[], Any]", module.get_database_summary)


@pytest.mark.django_db
def test_get_database_summary_reports_current_metadata() -> None:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.3680043.8.498.100",
        source_dataset="summary-test-dataset",
        source_subject_id="summary-test-subject",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.200",
        modality="CT",
        number_of_instances=1,
    )
    ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.300",
        instance_number=1,
        file_sha256="3" * 64,
    )
    IngestionJob.objects.create(
        status=IngestionJob.Status.COMPLETED,
        source_type=IngestionJob.SourceType.LOCAL_MANIFEST,
        source_name="summary-test-dataset",
        source_uri="metadata-only",
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    analysis_run = AnalysisRun.objects.create(
        study=study,
        status=AnalysisRun.Status.COMPLETED,
        name="Summary test analysis",
        algorithm_name="series_geometry_summary",
        algorithm_version="0.1.0",
    )
    MeasurementResult.objects.create(
        analysis_run=analysis_run,
        name="number_of_instances",
        value=Decimal("1.00000000"),
        unit="count",
    )

    summary = load_get_database_summary()()

    assert summary.studies_count == 1
    assert summary.series_count == 1
    assert summary.instances_count == 1
    assert summary.analysis_runs_count == 1
    assert summary.measurement_results_count == 1
    assert summary.modalities == ["CT"]
    assert summary.latest_ingestion_job_status == IngestionJob.Status.COMPLETED
    assert summary.latest_analysis_run_status == AnalysisRun.Status.COMPLETED
