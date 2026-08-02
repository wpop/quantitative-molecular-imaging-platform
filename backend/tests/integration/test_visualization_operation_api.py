"""Tests for controlled visualization artifact generation API."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analysis.models import VisualizationArtifact
from apps.analysis.visualization_execution import VisualizationExecutionError
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def registered_artifact() -> VisualizationArtifact:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.study",
        study_description="Visualization operation test study",
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
        rows=512,
        columns=512,
        file_sha256="0" * 64,
    )
    return VisualizationArtifact.objects.create(
        instance=instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=0,
        value_units="HU",
        relative_path="outputs/visualizations/test/ct_rescale_slice_0000.png",
        mime_type="image/png",
        file_size_bytes=2048,
        file_sha256="a" * 64,
        rows=512,
        columns=512,
        colormap="gray",
        display_minimum=-160.0,
        display_maximum=240.0,
        window_center=40.0,
        window_width=400.0,
        created_at=timezone.now(),
    )


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "series_instance_uid": "1.2.826.0.1.series",
        "operation": "rescale",
        "window_center": 40.0,
        "window_width": 400.0,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_generate_visualization_valid_request_returns_200(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(return_value=registered_artifact)
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(),
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_generate_visualization_response_uses_artifact_serializer(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.analysis.api.views.execute_visualization_request",
        Mock(return_value=registered_artifact),
    )

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(),
        format="json",
    )
    payload = response.json()

    assert payload["id"] == registered_artifact.id
    assert payload["instance_id"] == registered_artifact.instance_id
    assert payload["series_instance_uid"] == "1.2.826.0.1.series"
    assert payload["sop_instance_uid"] == "1.2.826.0.1.sop"
    assert payload["operation"] == "rescale"
    assert payload["image_url"].endswith(
        f"/api/v1/analysis/artifacts/{registered_artifact.id}/image/",
    )


@pytest.mark.django_db
def test_generate_visualization_response_does_not_expose_paths(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.analysis.api.views.execute_visualization_request",
        Mock(return_value=registered_artifact),
    )

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(),
        format="json",
    )
    response_text = response.content.decode()
    payload = response.json()

    assert "relative_path" not in payload
    assert "absolute_path" not in payload
    assert "outputs/visualizations" not in response_text
    assert "tmp/qmip" not in response_text


@pytest.mark.django_db
def test_generate_visualization_rescale_passes_validated_parameters(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(return_value=registered_artifact)
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(lower_percentile=2.0, upper_percentile=98.0, dpi=120),
        format="json",
    )

    execution.assert_called_once_with(
        series_instance_uid="1.2.826.0.1.series",
        operation="rescale",
        slice_index=None,
        gaussian_sigma=1.0,
        window_center=40.0,
        window_width=400.0,
        lower_percentile=2.0,
        upper_percentile=98.0,
        dpi=120,
    )


@pytest.mark.django_db
def test_generate_visualization_gaussian_passes_sigma(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(return_value=registered_artifact)
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(operation="gaussian", gaussian_sigma=1.5),
        format="json",
    )

    assert response.status_code == 200
    assert execution.call_args.kwargs["operation"] == "gaussian"
    assert execution.call_args.kwargs["gaussian_sigma"] == 1.5


@pytest.mark.django_db
def test_generate_visualization_sobel_is_accepted(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(return_value=registered_artifact)
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(operation="sobel"),
        format="json",
    )

    assert response.status_code == 200
    assert execution.call_args.kwargs["operation"] == "sobel"


@pytest.mark.django_db
def test_generate_visualization_passes_optional_slice_index(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(return_value=registered_artifact)
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(slice_index=3),
        format="json",
    )

    assert response.status_code == 200
    assert execution.call_args.kwargs["slice_index"] == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        valid_payload(operation="unsupported"),
        valid_payload(gaussian_sigma=0),
        valid_payload(window_width=0),
        valid_payload(lower_percentile=99, upper_percentile=1),
    ],
)
def test_generate_visualization_invalid_scientific_parameters_return_400(
    api_client: APIClient,
    payload: dict[str, object],
) -> None:
    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=payload,
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field",
    [
        "relative_path",
        "absolute_path",
        "dicom_path",
        "artifact_path",
        "instance_id",
        "image_bytes",
        "pixel_array",
        "result_array",
    ],
)
def test_generate_visualization_rejects_path_bytes_and_array_fields(
    api_client: APIClient,
    field: str,
) -> None:
    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(**{field: "not allowed"}),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_generate_visualization_controlled_failure_returns_safe_error(
    api_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(
        side_effect=VisualizationExecutionError("Visualization artifact could not be generated."),
    )
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(),
        format="json",
    )
    response_text = response.content.decode()

    assert response.status_code == 400
    assert response.json() == {"detail": "Visualization artifact could not be generated."}
    assert "outputs/visualizations" not in response_text
    assert "tmp/qmip" not in response_text


@pytest.mark.django_db
def test_generate_visualization_series_selection_failure_returns_404(
    api_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = Mock(
        side_effect=VisualizationExecutionError(
            "Requested imaging series could not be selected.",
            series_selection_failed=True,
        ),
    )
    monkeypatch.setattr("apps.analysis.api.views.execute_visualization_request", execution)

    response = api_client.post(
        "/api/v1/analysis/artifacts/generate/",
        data=valid_payload(),
        format="json",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Requested imaging series could not be selected."}


@pytest.mark.django_db
def test_existing_artifact_post_collection_remains_405(
    api_client: APIClient,
) -> None:
    response = api_client.post("/api/v1/analysis/artifacts/", data={}, format="json")

    assert response.status_code == 405


def test_existing_artifact_routes_remain_unchanged() -> None:
    assert reverse("analysis-api:visualization-artifact-list") == "/api/v1/analysis/artifacts/"
    assert (
        reverse("analysis-api:visualization-artifact-detail", kwargs={"pk": 7})
        == "/api/v1/analysis/artifacts/7/"
    )
    assert (
        reverse("analysis-api:visualization-artifact-image", kwargs={"pk": 7})
        == "/api/v1/analysis/artifacts/7/image/"
    )
    assert (
        reverse("analysis-api:visualization-artifact-generate")
        == "/api/v1/analysis/artifacts/generate/"
    )


@pytest.mark.django_db
def test_existing_artifact_list_and_detail_routes_still_return_metadata(
    api_client: APIClient,
    registered_artifact: VisualizationArtifact,
) -> None:
    list_response = api_client.get("/api/v1/analysis/artifacts/")
    detail_response = api_client.get(f"/api/v1/analysis/artifacts/{registered_artifact.id}/")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()[0]["id"] == registered_artifact.id
    assert detail_response.json()["id"] == registered_artifact.id
