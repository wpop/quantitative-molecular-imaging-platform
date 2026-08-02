#!/usr/bin/env python3
"""Ingest validated local DICOM header metadata into Django models.

This script reads local files only. It verifies checksums, reads DICOM headers
with stop_before_pixels=True, and stores metadata in the Django domain models.
It never downloads data, reads pixel arrays, or performs image analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import django
import pydicom
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from pydicom.errors import InvalidDicomError


DEFAULT_SETTINGS_MODULE = "config.settings.development"
COLLECTION = "CT-vs-PET-Ventilation-Imaging"
SUBJECT_ID = "CT-PET-VI-01"
STUDY_INSTANCE_UID = "1.3.6.1.4.1.14519.5.2.1.297577087050970310787702792940607009472"
RAW_SUBSET_DIR = Path("datasets/raw/tcia") / COLLECTION / SUBJECT_ID
CHECKSUM_PATH = Path("backend/tests/real_data/checksums.sha256")
VALIDATION_SUMMARY_PATH = Path(
    "backend/tests/real_data/metadata_candidates/local_dicom_validation_summary.json"
)
INGESTION_SUMMARY_PATH = Path(
    "backend/tests/real_data/metadata_candidates/local_dicom_ingestion_summary.json"
)
EXPECTED_TOTAL_FILES = 1149
BUFFER_SIZE = 1024 * 1024
HEADER_TAGS = [
    "AccessionNumber",
    "BodyPartExamined",
    "Columns",
    "ImageOrientationPatient",
    "ImagePositionPatient",
    "InstanceNumber",
    "Modality",
    "PatientID",
    "PixelSpacing",
    "Rows",
    "SOPClassUID",
    "SOPInstanceUID",
    "SeriesDescription",
    "SeriesInstanceUID",
    "SliceThickness",
    "StudyDate",
    "StudyDescription",
    "StudyInstanceUID",
]


@dataclass(frozen=True)
class ExpectedSeries:
    modality: str
    series_instance_uid: str
    expected_files: int


@dataclass(frozen=True)
class InstanceMetadata:
    file_path: Path
    file_sha256: str
    patient_id: str
    study_instance_uid: str
    series_instance_uid: str
    modality: str
    sop_instance_uid: str
    sop_class_uid: str
    instance_number: int | None
    rows: int | None
    columns: int | None
    accession_number: str
    study_description: str
    study_date: Any
    series_description: str
    body_part_examined: str
    image_orientation_patient: list[float] | None
    image_position_patient: list[float] | None
    pixel_spacing: list[float] | None
    slice_thickness: Decimal | None


EXPECTED_SERIES = (
    ExpectedSeries(
        modality="CT",
        series_instance_uid="1.3.6.1.4.1.14519.5.2.1.133320994602881796006698916833783151254",
        expected_files=990,
    ),
    ExpectedSeries(
        modality="PT",
        series_instance_uid="1.3.6.1.4.1.14519.5.2.1.246352124462042526540512717085218914533",
        expected_files=159,
    ),
)
EXPECTED_BY_SERIES_UID = {series.series_instance_uid: series for series in EXPECTED_SERIES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest validated local TCIA CT and PT DICOM header metadata into "
            "Django models. No data is downloaded and no pixel arrays are read."
        )
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_MODULE,
        help="Django settings module.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_SUBSET_DIR,
        help="Local selected raw DICOM subset directory.",
    )
    parser.add_argument(
        "--checksums",
        type=Path,
        default=CHECKSUM_PATH,
        help="SHA-256 checksum manifest for local selected DICOM files.",
    )
    parser.add_argument(
        "--validation-summary",
        type=Path,
        default=VALIDATION_SUMMARY_PATH,
        help="Existing local validation summary JSON.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=INGESTION_SUMMARY_PATH,
        help="Output JSON ingestion summary path.",
    )
    return parser.parse_args()


def setup_django(settings_module: str) -> None:
    repo_root = Path.cwd()
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


def read_checksum_manifest(path: Path) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError(f"Invalid checksum line {line_number}: {line}")
        digest, relative_path = parts
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
            raise RuntimeError(f"Invalid SHA-256 digest on line {line_number}: {digest}")
        entries.append((digest.lower(), Path(relative_path)))
    return entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(BUFFER_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(Path.cwd().resolve()).as_posix()


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError):
        return None


def parse_float_list(value: Any) -> list[float] | None:
    if value in (None, ""):
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def parse_study_date(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(str(value), "%Y%m%d").date()
    except ValueError:
        return None


def load_validation_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Validation summary does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Validation summary must be a JSON object.")
    if data.get("summary_status") != "passed":
        raise RuntimeError("Validation summary did not pass.")
    if data.get("validated_total_files") != EXPECTED_TOTAL_FILES:
        raise RuntimeError("Validation summary has an unexpected file count.")
    if data.get("pixel_data_read") is not False or data.get("network_calls_performed") is not False:
        raise RuntimeError("Validation summary does not describe local metadata-only validation.")
    return data


def validate_paths_under_raw_dir(entries: list[tuple[str, Path]], raw_dir: Path) -> None:
    raw_root = raw_dir.resolve()
    for _, relative_path in entries:
        resolved = relative_path.resolve()
        if raw_root != resolved and raw_root not in resolved.parents:
            raise RuntimeError(f"Checksum entry is outside the selected raw subset: {relative_path}")


def read_instance_metadata(file_path: Path, file_sha256: str) -> InstanceMetadata:
    # stop_before_pixels keeps this as header metadata ingestion, not image analysis.
    dataset = pydicom.dcmread(file_path, stop_before_pixels=True, specific_tags=HEADER_TAGS)
    metadata = InstanceMetadata(
        file_path=file_path,
        file_sha256=file_sha256,
        patient_id=str(dataset.get("PatientID", "")),
        study_instance_uid=str(dataset.get("StudyInstanceUID", "")),
        series_instance_uid=str(dataset.get("SeriesInstanceUID", "")),
        modality=str(dataset.get("Modality", "")),
        sop_instance_uid=str(dataset.get("SOPInstanceUID", "")),
        sop_class_uid=str(dataset.get("SOPClassUID", "")),
        instance_number=parse_int(dataset.get("InstanceNumber")),
        rows=parse_int(dataset.get("Rows")),
        columns=parse_int(dataset.get("Columns")),
        accession_number=str(dataset.get("AccessionNumber", "")),
        study_description=str(dataset.get("StudyDescription", "")),
        study_date=parse_study_date(dataset.get("StudyDate")),
        series_description=str(dataset.get("SeriesDescription", "")),
        body_part_examined=str(dataset.get("BodyPartExamined", "")),
        image_orientation_patient=parse_float_list(dataset.get("ImageOrientationPatient")),
        image_position_patient=parse_float_list(dataset.get("ImagePositionPatient")),
        pixel_spacing=parse_float_list(dataset.get("PixelSpacing")),
        slice_thickness=parse_decimal(dataset.get("SliceThickness")),
    )
    if metadata.study_instance_uid != STUDY_INSTANCE_UID:
        raise RuntimeError(f"Unexpected StudyInstanceUID in {file_path}")
    if metadata.patient_id != SUBJECT_ID:
        raise RuntimeError(f"Unexpected PatientID in {file_path}: {metadata.patient_id}")
    expected_series = EXPECTED_BY_SERIES_UID.get(metadata.series_instance_uid)
    if expected_series is None:
        raise RuntimeError(f"Unexpected SeriesInstanceUID in {file_path}: {metadata.series_instance_uid}")
    if metadata.modality != expected_series.modality:
        raise RuntimeError(f"Unexpected Modality in {file_path}: {metadata.modality}")
    if not metadata.sop_instance_uid:
        raise RuntimeError(f"Missing SOPInstanceUID in {file_path}")
    return metadata


def read_and_validate_instances(args: argparse.Namespace) -> list[InstanceMetadata]:
    if not args.raw_dir.exists():
        raise RuntimeError(f"Raw subset directory does not exist: {args.raw_dir}")
    if not args.checksums.exists():
        raise RuntimeError(f"Checksum file does not exist: {args.checksums}")

    load_validation_summary(args.validation_summary)
    entries = read_checksum_manifest(args.checksums)
    validate_paths_under_raw_dir(entries, args.raw_dir)
    if len(entries) != EXPECTED_TOTAL_FILES:
        raise RuntimeError(f"Checksum manifest lists {len(entries)} files, expected {EXPECTED_TOTAL_FILES}.")

    instances: list[InstanceMetadata] = []
    seen_sop_instance_uids: set[str] = set()
    series_counts = {series.series_instance_uid: 0 for series in EXPECTED_SERIES}

    for expected_digest, relative_path in entries:
        if not relative_path.exists():
            raise RuntimeError(f"Listed file does not exist: {relative_path}")
        actual_digest = sha256_file(relative_path)
        if actual_digest != expected_digest:
            raise RuntimeError(f"Checksum mismatch for {relative_path}")
        try:
            metadata = read_instance_metadata(relative_path, actual_digest)
        except InvalidDicomError as exc:
            raise RuntimeError(f"Invalid DICOM file: {relative_path}") from exc
        if metadata.sop_instance_uid in seen_sop_instance_uids:
            raise RuntimeError(f"Duplicate SOPInstanceUID in local subset: {metadata.sop_instance_uid}")
        seen_sop_instance_uids.add(metadata.sop_instance_uid)
        instances.append(metadata)
        series_counts[metadata.series_instance_uid] += 1

    for series in EXPECTED_SERIES:
        actual_count = series_counts[series.series_instance_uid]
        if actual_count != series.expected_files:
            raise RuntimeError(
                f"{series.modality} series count is {actual_count}, expected {series.expected_files}."
            )
    return instances


def first_metadata(instances: list[InstanceMetadata]) -> InstanceMetadata:
    if not instances:
        raise RuntimeError("No DICOM metadata was available to ingest.")
    return instances[0]


def first_series_metadata(instances: list[InstanceMetadata], series_uid: str) -> InstanceMetadata:
    for metadata in instances:
        if metadata.series_instance_uid == series_uid:
            return metadata
    raise RuntimeError(f"No metadata found for series {series_uid}")


def create_event(job: Any, message: str, context: dict[str, Any] | None = None) -> None:
    from apps.ingestion.models import IngestionJobEvent

    IngestionJobEvent.objects.create(
        job=job,
        level=IngestionJobEvent.Level.INFO,
        message=message,
        context=context or {},
    )


def register_local_dicom_file(
    instance: Any,
    file_path: Path,
    file_sha256: str,
    repo_root: Path | None = None,
) -> Any:
    """Create or update the local file registry row for one imaging instance."""

    from apps.imaging.models import LocalDicomFile

    root = (repo_root or Path.cwd()).resolve()
    relative_path = file_path.resolve().relative_to(root).as_posix()
    local_file, _ = LocalDicomFile.objects.update_or_create(
        instance=instance,
        defaults={
            "relative_path": relative_path,
            "file_sha256": file_sha256,
            "file_size_bytes": file_path.stat().st_size,
            "is_available": True,
        },
    )
    return local_file


def ingest_instances(args: argparse.Namespace, instances: list[InstanceMetadata]) -> dict[str, Any]:
    from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy, LocalDicomFile
    from apps.ingestion.models import IngestionJob

    study_metadata = first_metadata(instances)
    series_counts = {series.series_instance_uid: 0 for series in EXPECTED_SERIES}
    for metadata in instances:
        series_counts[metadata.series_instance_uid] += 1

    with transaction.atomic():
        job = IngestionJob.objects.create(
            status=IngestionJob.Status.RUNNING,
            source_type=IngestionJob.SourceType.LOCAL_MANIFEST,
            source_name=COLLECTION,
            source_uri=relative_to_repo(args.raw_dir),
            started_at=timezone.now(),
        )
        create_event(job, "Started local DICOM metadata ingestion.", {"expected_total_files": EXPECTED_TOTAL_FILES})
        create_event(
            job,
            "Validated local checksums and DICOM headers before ingestion.",
            {"validated_files": len(instances)},
        )

        study, _ = ImagingStudy.objects.update_or_create(
            study_instance_uid=STUDY_INSTANCE_UID,
            defaults={
                "accession_number": study_metadata.accession_number,
                "study_description": study_metadata.study_description,
                "modality_summary": "CT,PT",
                "study_date": study_metadata.study_date,
                "source_dataset": COLLECTION,
                "source_subject_id": SUBJECT_ID,
            },
        )

        series_models = {}
        for expected_series in EXPECTED_SERIES:
            metadata = first_series_metadata(instances, expected_series.series_instance_uid)
            series_model, _ = ImagingSeries.objects.update_or_create(
                series_instance_uid=expected_series.series_instance_uid,
                defaults={
                    "study": study,
                    "modality": expected_series.modality,
                    "series_description": metadata.series_description,
                    "body_part_examined": metadata.body_part_examined,
                    "image_orientation_patient": metadata.image_orientation_patient,
                    "image_position_patient": metadata.image_position_patient,
                    "pixel_spacing": metadata.pixel_spacing,
                    "slice_thickness": metadata.slice_thickness,
                    "number_of_instances": series_counts[expected_series.series_instance_uid],
                },
            )
            series_models[expected_series.series_instance_uid] = series_model

        for metadata in instances:
            instance_model, _ = ImagingInstance.objects.update_or_create(
                sop_instance_uid=metadata.sop_instance_uid,
                defaults={
                    "series": series_models[metadata.series_instance_uid],
                    "sop_class_uid": metadata.sop_class_uid,
                    "instance_number": metadata.instance_number,
                    "rows": metadata.rows,
                    "columns": metadata.columns,
                    "file_sha256": metadata.file_sha256,
                    "orthanc_instance_id": "",
                },
            )
            register_local_dicom_file(
                instance=instance_model,
                file_path=metadata.file_path,
                file_sha256=metadata.file_sha256,
            )

        db_study_count = ImagingStudy.objects.filter(study_instance_uid=STUDY_INSTANCE_UID).count()
        db_series_count = ImagingSeries.objects.filter(
            series_instance_uid__in=[series.series_instance_uid for series in EXPECTED_SERIES]
        ).count()
        db_instance_count = ImagingInstance.objects.filter(
            series__series_instance_uid__in=[series.series_instance_uid for series in EXPECTED_SERIES]
        ).count()
        db_local_file_count = LocalDicomFile.objects.filter(
            instance__series__series_instance_uid__in=[
                series.series_instance_uid for series in EXPECTED_SERIES
            ]
        ).count()
        db_available_file_count = LocalDicomFile.objects.filter(
            instance__series__series_instance_uid__in=[
                series.series_instance_uid for series in EXPECTED_SERIES
            ],
            is_available=True,
        ).count()
        if db_study_count != 1 or db_series_count != 2 or db_instance_count != EXPECTED_TOTAL_FILES:
            raise RuntimeError(
                "Database validation failed after ingestion: "
                f"{db_study_count} studies, {db_series_count} series, {db_instance_count} instances."
            )
        if db_local_file_count != EXPECTED_TOTAL_FILES or db_available_file_count != EXPECTED_TOTAL_FILES:
            raise RuntimeError(
                "Local file registry validation failed after ingestion: "
                f"{db_local_file_count} registered, {db_available_file_count} available."
            )

        create_event(
            job,
            "Ingested local DICOM metadata summary.",
            {
                "studies": db_study_count,
                "series": db_series_count,
                "instances": db_instance_count,
                "local_dicom_files": db_local_file_count,
                "available_local_dicom_files": db_available_file_count,
            },
        )
        job.status = IngestionJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "completed_at", "updated_at"])
        create_event(job, "Completed local DICOM metadata ingestion.")

    return {
        "collection": COLLECTION,
        "subject_id": SUBJECT_ID,
        "study_instance_uid": STUDY_INSTANCE_UID,
        "local_only": True,
        "network_calls_performed": False,
        "pixel_data_read": False,
        "image_analysis_performed": False,
        "raw_dicom_stored_in_git": False,
        "source_directory": relative_to_repo(args.raw_dir),
        "checksum_file": relative_to_repo(args.checksums),
        "validation_summary": relative_to_repo(args.validation_summary),
        "ingestion_job_id": job.id,
        "studies_registered": db_study_count,
        "series_registered": db_series_count,
        "instances_registered": db_instance_count,
        "local_dicom_files_registered": db_local_file_count,
        "local_dicom_files_available": db_available_file_count,
        "series": [
            {
                "modality": series.modality,
                "series_instance_uid": series.series_instance_uid,
                "instances_registered": series_counts[series.series_instance_uid],
            }
            for series in EXPECTED_SERIES
        ],
    }


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mark_failed_job(settings_module: str, raw_dir: Path, error_message: str) -> None:
    try:
        setup_django(settings_module)
        from apps.ingestion.models import IngestionJob, IngestionJobEvent

        job = IngestionJob.objects.create(
            status=IngestionJob.Status.FAILED,
            source_type=IngestionJob.SourceType.LOCAL_MANIFEST,
            source_name=COLLECTION,
            source_uri=relative_to_repo(raw_dir),
            started_at=timezone.now(),
            completed_at=timezone.now(),
            error_message=error_message,
        )
        IngestionJobEvent.objects.create(
            job=job,
            level=IngestionJobEvent.Level.ERROR,
            message="Local DICOM metadata ingestion failed.",
            context={"error": error_message},
        )
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    try:
        setup_django(args.settings)
        instances = read_and_validate_instances(args)
        summary = ingest_instances(args, instances)
        write_summary(args.summary_path, summary)
    except (OSError, RuntimeError, InvalidDicomError, ImproperlyConfigured) as exc:
        mark_failed_job(args.settings, args.raw_dir, str(exc))
        print(f"Local DICOM metadata ingestion failed: {exc}", file=sys.stderr)
        return 1

    print("Local DICOM metadata ingestion completed.")
    print(f"Studies registered: {summary['studies_registered']}")
    print(f"Series registered: {summary['series_registered']}")
    print(f"Instances registered: {summary['instances_registered']}")
    print(f"Local DICOM files registered: {summary['local_dicom_files_registered']}")
    print(f"Local DICOM files available: {summary['local_dicom_files_available']}")
    print(f"Ingestion job id: {summary['ingestion_job_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
