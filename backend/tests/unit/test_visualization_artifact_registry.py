"""Tests for visualization artifact registry metadata."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.analysis.artifact_registry import (
    VisualizationArtifactRegistryError,
    register_visualization_artifact,
)
from apps.analysis.models import VisualizationArtifact
from apps.analysis.scientific_operations import ScientificOperation
from apps.analysis.visualization import VisualizationArtifactResult
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy


@pytest.fixture
def imaging_instance() -> ImagingInstance:
    study = ImagingStudy.objects.create(study_instance_uid="1.2.826.0.1.study")
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.series",
        modality="CT",
        number_of_instances=1,
    )
    return ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.sop",
        instance_number=1,
        rows=2,
        columns=3,
        file_sha256="1" * 64,
    )


def artifact_result(
    instance: ImagingInstance,
    *,
    relative_png_path: str = "outputs/visualizations/03ea7c3877b4/ct_rescale_slice_0495.png",
    sop_instance_uid: str | None = None,
    series_instance_uid: str | None = None,
    study_instance_uid: str | None = None,
    file_size_bytes: int = 1234,
    sha256: str = "a" * 64,
) -> VisualizationArtifactResult:
    return VisualizationArtifactResult(
        operation=ScientificOperation.RESCALE,
        study_instance_uid=study_instance_uid or instance.series.study.study_instance_uid,
        series_instance_uid=series_instance_uid or instance.series.series_instance_uid,
        sop_instance_uid=sop_instance_uid or instance.sop_instance_uid,
        instance_id=instance.id,
        slice_index=495,
        modality="CT",
        value_units="HU",
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
        window_center=0.0,
        window_width=400.0,
        relative_png_path=relative_png_path,
        mime_type="image/png",
        file_size_bytes=file_size_bytes,
        sha256=sha256,
    )


@pytest.mark.django_db
def test_visualization_artifact_accepts_valid_outputs_visualizations_path(
    imaging_instance: ImagingInstance,
) -> None:
    artifact = VisualizationArtifact(
        instance=imaging_instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=1,
        value_units="HU",
        relative_path="outputs/visualizations/03ea7c3877b4/ct_rescale_slice_0001.png",
        file_size_bytes=100,
        file_sha256="a" * 64,
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
        window_center=0.0,
        window_width=400.0,
    )

    artifact.full_clean()


@pytest.mark.django_db
def test_visualization_artifact_rejects_absolute_path(
    imaging_instance: ImagingInstance,
) -> None:
    artifact = VisualizationArtifact(
        instance=imaging_instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=1,
        value_units="HU",
        relative_path="/home/user/result.png",
        file_size_bytes=100,
        file_sha256="a" * 64,
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
    )

    with pytest.raises(ValidationError, match="relative"):
        artifact.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "relative_path",
    [
        "../result.png",
        "outputs/../result.png",
    ],
)
def test_visualization_artifact_rejects_parent_traversal(
    imaging_instance: ImagingInstance,
    relative_path: str,
) -> None:
    artifact = VisualizationArtifact(
        instance=imaging_instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=1,
        value_units="HU",
        relative_path=relative_path,
        file_size_bytes=100,
        file_sha256="a" * 64,
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
    )

    with pytest.raises(ValidationError, match="parent traversal"):
        artifact.full_clean()


@pytest.mark.django_db
def test_visualization_artifact_rejects_path_outside_visualizations(
    imaging_instance: ImagingInstance,
) -> None:
    artifact = VisualizationArtifact(
        instance=imaging_instance,
        operation=VisualizationArtifact.Operation.RESCALE,
        modality="CT",
        slice_index=1,
        value_units="HU",
        relative_path="datasets/raw/result.png",
        file_size_bytes=100,
        file_sha256="a" * 64,
        rows=2,
        columns=3,
        colormap="gray",
        display_minimum=-200.0,
        display_maximum=200.0,
    )

    with pytest.raises(ValidationError, match="outputs/visualizations"):
        artifact.full_clean()


@pytest.mark.django_db
def test_register_visualization_artifact_creates_row(
    imaging_instance: ImagingInstance,
) -> None:
    artifact = register_visualization_artifact(artifact_result(imaging_instance))

    assert artifact.id is not None
    assert VisualizationArtifact.objects.count() == 1


@pytest.mark.django_db
def test_register_visualization_artifact_stores_expected_metadata(
    imaging_instance: ImagingInstance,
) -> None:
    result = artifact_result(imaging_instance)

    artifact = register_visualization_artifact(result)

    assert artifact.instance == imaging_instance
    assert artifact.operation == "rescale"
    assert artifact.modality == "CT"
    assert artifact.slice_index == 495
    assert artifact.value_units == "HU"
    assert artifact.relative_path == result.relative_png_path
    assert artifact.mime_type == "image/png"
    assert artifact.file_size_bytes == result.file_size_bytes
    assert artifact.file_sha256 == result.sha256
    assert artifact.rows == 2
    assert artifact.columns == 3
    assert artifact.colormap == "gray"
    assert artifact.display_minimum == -200.0
    assert artifact.display_maximum == 200.0
    assert artifact.window_center == 0.0
    assert artifact.window_width == 400.0


@pytest.mark.django_db
def test_register_visualization_artifact_updates_existing_relative_path(
    imaging_instance: ImagingInstance,
) -> None:
    first = register_visualization_artifact(artifact_result(imaging_instance))
    second = register_visualization_artifact(
        artifact_result(imaging_instance, file_size_bytes=9999, sha256="b" * 64),
    )

    assert second.id == first.id
    assert VisualizationArtifact.objects.count() == 1
    assert second.file_size_bytes == 9999
    assert second.file_sha256 == "b" * 64


@pytest.mark.django_db
def test_register_visualization_artifact_rejects_sop_instance_uid_mismatch(
    imaging_instance: ImagingInstance,
) -> None:
    result = artifact_result(imaging_instance, sop_instance_uid="1.2.bad.sop")

    with pytest.raises(VisualizationArtifactRegistryError, match="SOPInstanceUID"):
        register_visualization_artifact(result)


@pytest.mark.django_db
def test_register_visualization_artifact_rejects_series_instance_uid_mismatch(
    imaging_instance: ImagingInstance,
) -> None:
    result = artifact_result(imaging_instance, series_instance_uid="1.2.bad.series")

    with pytest.raises(VisualizationArtifactRegistryError, match="SeriesInstanceUID"):
        register_visualization_artifact(result)


@pytest.mark.django_db
def test_register_visualization_artifact_rejects_study_instance_uid_mismatch(
    imaging_instance: ImagingInstance,
) -> None:
    result = artifact_result(imaging_instance, study_instance_uid="1.2.bad.study")

    with pytest.raises(VisualizationArtifactRegistryError, match="StudyInstanceUID"):
        register_visualization_artifact(result)


def test_visualization_artifact_model_contains_no_array_or_absolute_path_field() -> None:
    field_names = {
        field.name for field in VisualizationArtifact._meta.get_fields()  # noqa: SLF001
    }

    assert "result_array" not in field_names
    assert "pixel_array" not in field_names
    assert "absolute_path" not in field_names
