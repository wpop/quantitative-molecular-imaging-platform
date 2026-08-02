"""Tests for read-only visualization artifact API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, cast

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analysis.models import VisualizationArtifact
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy

if TYPE_CHECKING:
    from pathlib import Path

PNG_BYTES = b"\x89PNG\r\n\x1a\nvisualization-test-png"


class ArtifactObjects(TypedDict):
    study: ImagingStudy
    series: ImagingSeries
    instance: ImagingInstance
    artifact: VisualizationArtifact
    relative_path: str


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def artifact_objects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ArtifactObjects:
    monkeypatch.setattr("apps.analysis.api.artifact_files.default_repo_root", lambda: tmp_path)
    relative_path = "outputs/visualizations/03ea7c3877b4/ct_rescale_slice_0001.png"
    png_path = tmp_path / relative_path
    png_path.parent.mkdir(parents=True)
    png_path.write_bytes(PNG_BYTES)

    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.study",
        study_description="Artifact API test study",
        modality_summary="CT",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.series",
        modality="CT",
        number_of_instances=1,
    )
    instance = ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.sop",
        instance_number=1,
        rows=2,
        columns=3,
        file_sha256="0" * 64,
    )
    artifact = VisualizationArtifact.objects.create(
        instance=instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=1,
        value_units="HU",
        relative_path=relative_path,
        mime_type="image/png",
        file_size_bytes=len(PNG_BYTES),
        file_sha256="a" * 64,
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
        window_center=0.0,
        window_width=400.0,
        created_at=timezone.now(),
    )
    return {
        "study": study,
        "series": series,
        "instance": instance,
        "artifact": artifact,
        "relative_path": relative_path,
    }


@pytest.mark.django_db
def test_artifact_list_returns_registered_metadata(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    response = api_client.get("/api/v1/analysis/artifacts/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["operation"] == "rescale"


@pytest.mark.django_db
def test_artifact_detail_returns_one_record(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == artifact.id


@pytest.mark.django_db
def test_artifact_serializer_includes_uids_and_image_url(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/")
    payload = response.json()

    assert payload["study_instance_uid"] == artifact_objects["study"].study_instance_uid
    assert payload["series_instance_uid"] == artifact_objects["series"].series_instance_uid
    assert payload["sop_instance_uid"] == artifact_objects["instance"].sop_instance_uid
    assert payload["image_url"].endswith(f"/api/v1/analysis/artifacts/{artifact.id}/image/")


@pytest.mark.django_db
def test_artifact_json_does_not_expose_paths_arrays_or_bytes(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/")
    payload = response.json()

    assert "relative_path" not in payload
    assert "absolute_path" not in payload
    assert "result_array" not in payload
    assert "pixel_array" not in payload
    assert "png_bytes" not in payload


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "matching_value", "nonmatching_value"),
    [
        ("series_instance_uid", "1.2.826.0.1.series", "1.2.826.0.1.other-series"),
        ("sop_instance_uid", "1.2.826.0.1.sop", "1.2.826.0.1.other-sop"),
        ("operation", "rescale", "sobel"),
        ("modality", "CT", "PT"),
    ],
)
def test_artifact_filters_are_applied(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
    query: str,
    matching_value: str,
    nonmatching_value: str,
) -> None:
    matching_response = api_client.get("/api/v1/analysis/artifacts/", {query: matching_value})
    nonmatching_response = api_client.get(
        "/api/v1/analysis/artifacts/",
        {query: nonmatching_value},
    )

    assert matching_response.status_code == 200
    assert len(matching_response.json()) == 1
    assert nonmatching_response.status_code == 200
    assert len(nonmatching_response.json()) == 0


@pytest.mark.django_db
def test_artifact_collection_rejects_post(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    response = api_client.post("/api/v1/analysis/artifacts/", data={})

    assert response.status_code == 405


@pytest.mark.django_db
def test_artifact_png_endpoint_returns_png_bytes(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/image/")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["Content-Disposition"].startswith("inline;")
    assert b"".join(cast("Any", response).streaming_content) == PNG_BYTES


@pytest.mark.django_db
def test_missing_png_returns_controlled_404(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]
    artifact.relative_path = "outputs/visualizations/03ea7c3877b4/missing.png"
    artifact.save(update_fields=["relative_path"])

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/image/")

    assert response.status_code == 404
    assert "outputs/visualizations" not in response.content.decode()


@pytest.mark.django_db
def test_unsafe_registered_path_is_not_served(
    api_client: APIClient,
    artifact_objects: ArtifactObjects,
) -> None:
    artifact = artifact_objects["artifact"]
    artifact.relative_path = "../unsafe.png"
    artifact.save(update_fields=["relative_path"])

    response = api_client.get(f"/api/v1/analysis/artifacts/{artifact.id}/image/")

    assert response.status_code == 404
    assert "unsafe.png" not in response.content.decode()
