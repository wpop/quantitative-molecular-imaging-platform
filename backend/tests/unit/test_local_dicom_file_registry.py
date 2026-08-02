"""Tests for local DICOM file registry metadata."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy, LocalDicomFile

if TYPE_CHECKING:
    from collections.abc import Callable


def load_register_local_dicom_file() -> Callable[..., Any]:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "ingest_local_dicom_metadata.py"
    spec = importlib.util.spec_from_file_location("ingest_local_dicom_metadata", script_path)
    if spec is None or spec.loader is None:
        message = f"Unable to load local ingestion script: {script_path}"
        raise RuntimeError(message)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast("Callable[..., Any]", module.register_local_dicom_file)


@pytest.fixture
def imaging_instance() -> ImagingInstance:
    study = ImagingStudy.objects.create(
        study_instance_uid="1.2.826.0.1.3680043.8.498.500",
        source_dataset="registry-test-dataset",
        source_subject_id="registry-test-subject",
    )
    series = ImagingSeries.objects.create(
        study=study,
        series_instance_uid="1.2.826.0.1.3680043.8.498.501",
        modality="CT",
        number_of_instances=1,
    )
    return ImagingInstance.objects.create(
        series=series,
        sop_instance_uid="1.2.826.0.1.3680043.8.498.502",
        instance_number=1,
        file_sha256="5" * 64,
    )


@pytest.mark.django_db
def test_local_dicom_file_accepts_repository_relative_path(
    imaging_instance: ImagingInstance,
) -> None:
    local_file = LocalDicomFile(
        instance=imaging_instance,
        relative_path="datasets/raw/tcia/collection/subject/file.dcm",
        file_sha256="a" * 64,
        file_size_bytes=128,
    )

    local_file.full_clean()
    local_file.save()

    assert local_file.id is not None
    assert local_file.is_available is True


@pytest.mark.django_db
def test_local_dicom_file_rejects_absolute_path(imaging_instance: ImagingInstance) -> None:
    local_file = LocalDicomFile(
        instance=imaging_instance,
        relative_path="/home/user/file.dcm",
        file_sha256="a" * 64,
        file_size_bytes=128,
    )

    with pytest.raises(ValidationError):
        local_file.full_clean()


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside/file.dcm",
        "datasets/raw/../../outside/file.dcm",
    ],
)
@pytest.mark.django_db
def test_local_dicom_file_rejects_parent_traversal_path(
    imaging_instance: ImagingInstance,
    relative_path: str,
) -> None:
    local_file = LocalDicomFile(
        instance=imaging_instance,
        relative_path=relative_path,
        file_sha256="a" * 64,
        file_size_bytes=128,
    )

    with pytest.raises(ValidationError):
        local_file.full_clean()


@pytest.mark.django_db
def test_imaging_instance_can_have_only_one_local_dicom_file(
    imaging_instance: ImagingInstance,
) -> None:
    LocalDicomFile.objects.create(
        instance=imaging_instance,
        relative_path="datasets/raw/tcia/collection/subject/file-1.dcm",
        file_sha256="a" * 64,
        file_size_bytes=128,
    )

    with pytest.raises(IntegrityError):
        LocalDicomFile.objects.create(
            instance=imaging_instance,
            relative_path="datasets/raw/tcia/collection/subject/file-2.dcm",
            file_sha256="b" * 64,
            file_size_bytes=256,
        )


@pytest.mark.django_db
def test_register_local_dicom_file_stores_relative_path_and_file_metadata(
    imaging_instance: ImagingInstance,
    tmp_path: Path,
) -> None:
    register_local_dicom_file = load_register_local_dicom_file()
    file_path = tmp_path / "datasets" / "raw" / "tcia" / "collection" / "subject" / "file.dcm"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"metadata-only test file")

    local_file = register_local_dicom_file(
        instance=imaging_instance,
        file_path=file_path,
        file_sha256="c" * 64,
        repo_root=tmp_path,
    )

    assert local_file.relative_path == "datasets/raw/tcia/collection/subject/file.dcm"
    assert local_file.file_sha256 == "c" * 64
    assert local_file.file_size_bytes == file_path.stat().st_size
    assert local_file.is_available is True


@pytest.mark.django_db
def test_register_local_dicom_file_updates_existing_record(
    imaging_instance: ImagingInstance,
    tmp_path: Path,
) -> None:
    register_local_dicom_file = load_register_local_dicom_file()
    first_path = tmp_path / "datasets" / "raw" / "tcia" / "collection" / "subject" / "file-1.dcm"
    second_path = tmp_path / "datasets" / "raw" / "tcia" / "collection" / "subject" / "file-2.dcm"
    first_path.parent.mkdir(parents=True)
    first_path.write_bytes(b"first metadata-only test file")
    second_path.write_bytes(b"second metadata-only test file")

    first_local_file = register_local_dicom_file(
        instance=imaging_instance,
        file_path=first_path,
        file_sha256="d" * 64,
        repo_root=tmp_path,
    )
    second_local_file = register_local_dicom_file(
        instance=imaging_instance,
        file_path=second_path,
        file_sha256="e" * 64,
        repo_root=tmp_path,
    )

    assert LocalDicomFile.objects.count() == 1
    assert second_local_file.id == first_local_file.id
    assert second_local_file.relative_path == "datasets/raw/tcia/collection/subject/file-2.dcm"
    assert second_local_file.file_sha256 == "e" * 64
    assert second_local_file.file_size_bytes == second_path.stat().st_size
    assert second_local_file.is_available is True
