"""Tests for read-only metadata API endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analysis.models import AnalysisRun, MeasurementResult
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy
from apps.ingestion.models import IngestionJob, IngestionJobEvent


class MetadataObjects(TypedDict):
    study: ImagingStudy
    series: ImagingSeries
    instance: ImagingInstance
    job: IngestionJob
    event: IngestionJobEvent
    analysis_run: AnalysisRun
    measurement_result: MeasurementResult


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def metadata_objects() -> MetadataObjects:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.3680043.8.498.1",
        study_description="Metadata API test study",
        modality_summary="CT",
        source_dataset="test-dataset",
        source_subject_id="test-subject",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.2",
        modality="CT",
        series_description="Metadata API test series",
        number_of_instances=1,
    )
    instance = ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.3",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
        instance_number=1,
        rows=512,
        columns=512,
        file_sha256="0" * 64,
    )
    job = IngestionJob.objects.create(
        status=IngestionJob.Status.COMPLETED,
        source_type=IngestionJob.SourceType.LOCAL_MANIFEST,
        source_name="test-dataset",
        source_uri="metadata-only",
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    event = IngestionJobEvent.objects.create(
        job=job,
        level=IngestionJobEvent.Level.INFO,
        message="Test event",
        context={"records": 1},
    )
    analysis_run = AnalysisRun.objects.create(
        study=study,
        status=AnalysisRun.Status.COMPLETED,
        name="Metadata API test analysis",
        algorithm_name="series_geometry_summary",
        algorithm_version="0.1.0",
        parameters={"metadata_only": True},
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    measurement_result = MeasurementResult.objects.create(
        analysis_run=analysis_run,
        name="approximate_in_plane_width",
        value=Decimal("512.00000000"),
        unit="mm",
        region_label=series.series_instance_uid,
        metadata={
            "modality": "CT",
            "series_instance_uid": series.series_instance_uid,
        },
    )
    return {
        "study": study,
        "series": series,
        "instance": instance,
        "job": job,
        "event": event,
        "analysis_run": analysis_run,
        "measurement_result": measurement_result,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/imaging/studies/",
        "/api/v1/imaging/series/",
        "/api/v1/imaging/instances/",
        "/api/v1/ingestion/jobs/",
        "/api/v1/analysis/runs/",
        "/api/v1/analysis/results/",
        "/api/v1/overview/",
    ],
)
def test_list_endpoints_return_200(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
    path: str,
) -> None:
    response = api_client.get(path)

    assert response.status_code == 200
    assert response.json()


@pytest.mark.django_db
def test_overview_endpoint_returns_expected_summary(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    response = api_client.get("/api/v1/overview/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["studies_count"] == 1
    assert payload["series_count"] == 1
    assert payload["instances_count"] == 1
    assert payload["modalities"] == ["CT"]
    assert payload["source_datasets"] == ["test-dataset"]
    assert payload["source_subjects"] == ["test-subject"]
    assert payload["ingestion_jobs_count"] == 1
    assert payload["latest_ingestion_status"] == IngestionJob.Status.COMPLETED
    assert payload["latest_ingestion_started_at"] is not None
    assert payload["latest_ingestion_completed_at"] is not None


@pytest.mark.django_db
def test_overview_endpoint_rejects_post(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    response = api_client.post("/api/v1/overview/", data={})

    assert response.status_code == 405


@pytest.mark.django_db
def test_retrieve_endpoint_returns_200(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    study = metadata_objects["study"]

    response = api_client.get(f"/api/v1/imaging/studies/{study.id}/")

    assert response.status_code == 200
    assert response.json()["study_instance_uid"] == study.study_instance_uid


@pytest.mark.django_db
def test_analysis_retrieve_endpoints_return_200(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    analysis_run = metadata_objects["analysis_run"]
    measurement_result = metadata_objects["measurement_result"]

    run_response = api_client.get(f"/api/v1/analysis/runs/{analysis_run.id}/")
    result_response = api_client.get(f"/api/v1/analysis/results/{measurement_result.id}/")

    assert run_response.status_code == 200
    assert run_response.json()["study_instance_uid"] == analysis_run.study.study_instance_uid
    assert result_response.status_code == 200
    assert result_response.json()["algorithm_name"] == analysis_run.algorithm_name


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/imaging/studies/"),
        ("put", "/api/v1/imaging/studies/{study_id}/"),
        ("patch", "/api/v1/imaging/studies/{study_id}/"),
        ("delete", "/api/v1/imaging/studies/{study_id}/"),
    ],
)
def test_write_methods_are_not_allowed(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
    method: str,
    path: str,
) -> None:
    study = metadata_objects["study"]
    resolved_path = path.format(study_id=study.id)
    request = getattr(api_client, method)

    response = request(resolved_path, data={})

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/analysis/runs/"),
        ("put", "/api/v1/analysis/runs/{analysis_run_id}/"),
        ("patch", "/api/v1/analysis/runs/{analysis_run_id}/"),
        ("delete", "/api/v1/analysis/runs/{analysis_run_id}/"),
        ("post", "/api/v1/analysis/results/"),
        ("put", "/api/v1/analysis/results/{measurement_result_id}/"),
        ("patch", "/api/v1/analysis/results/{measurement_result_id}/"),
        ("delete", "/api/v1/analysis/results/{measurement_result_id}/"),
    ],
)
def test_analysis_write_methods_are_not_allowed(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
    method: str,
    path: str,
) -> None:
    analysis_run = metadata_objects["analysis_run"]
    measurement_result = metadata_objects["measurement_result"]
    resolved_path = path.format(
        analysis_run_id=analysis_run.id,
        measurement_result_id=measurement_result.id,
    )
    request = getattr(api_client, method)

    response = request(resolved_path, data={})

    assert response.status_code == 405


@pytest.mark.django_db
def test_manual_filters_are_applied(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    response = api_client.get(
        "/api/v1/imaging/series/",
        {
            "study_instance_uid": "1.2.826.0.1.3680043.8.498.1",
            "modality": "CT",
            "source_dataset": "test-dataset",
            "source_subject_id": "test-subject",
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_analysis_manual_filters_are_applied(
    api_client: APIClient,
    metadata_objects: MetadataObjects,
) -> None:
    study = metadata_objects["study"]

    run_response = api_client.get(
        "/api/v1/analysis/runs/",
        {
            "status": AnalysisRun.Status.COMPLETED,
            "algorithm_name": "series_geometry_summary",
            "algorithm_version": "0.1.0",
            "study_instance_uid": study.study_instance_uid,
        },
    )
    result_response = api_client.get(
        "/api/v1/analysis/results/",
        {
            "status": AnalysisRun.Status.COMPLETED,
            "algorithm_name": "series_geometry_summary",
            "algorithm_version": "0.1.0",
            "study_instance_uid": study.study_instance_uid,
            "name": "approximate_in_plane_width",
            "unit": "mm",
            "modality": "CT",
        },
    )

    assert run_response.status_code == 200
    assert len(run_response.json()) == 1
    assert result_response.status_code == 200
    assert len(result_response.json()) == 1
