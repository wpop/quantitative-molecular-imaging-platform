#!/usr/bin/env python3
"""Validate the local selected TCIA/NBIA DICOM subset.

This script reads local files only. It validates checksums and DICOM header
metadata for the selected CT and PT series without reading pixel arrays or
performing image analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pydicom
from pydicom.errors import InvalidDicomError


COLLECTION = "CT-vs-PET-Ventilation-Imaging"
SUBJECT_ID = "CT-PET-VI-01"
STUDY_INSTANCE_UID = "1.3.6.1.4.1.14519.5.2.1.297577087050970310787702792940607009472"
RAW_SUBSET_DIR = Path("datasets/raw/tcia") / COLLECTION / SUBJECT_ID
CHECKSUM_PATH = Path("backend/tests/real_data/checksums.sha256")
SUMMARY_PATH = Path("backend/tests/real_data/metadata_candidates/local_dicom_validation_summary.json")
BUFFER_SIZE = 1024 * 1024
EXPECTED_TOTAL_FILES = 1149
HEADER_TAGS = ["StudyInstanceUID", "SeriesInstanceUID", "Modality"]


@dataclass(frozen=True)
class ExpectedSeries:
    modality: str
    series_instance_uid: str
    expected_files: int


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
            "Validate the local selected TCIA CT and PT DICOM subset using "
            "SHA-256 checksums and DICOM headers only. No data is downloaded."
        )
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_SUBSET_DIR,
        help="Local raw selected DICOM subset directory.",
    )
    parser.add_argument(
        "--checksums",
        type=Path,
        default=CHECKSUM_PATH,
        help="SHA-256 checksum manifest for the local selected subset.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=SUMMARY_PATH,
        help="Output JSON validation summary path.",
    )
    return parser.parse_args()


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


def is_dicom_preamble(path: Path) -> bool:
    with path.open("rb") as handle:
        header = handle.read(132)
    return len(header) >= 132 and header[128:132] == b"DICM"


def read_header(path: Path) -> dict[str, str]:
    # stop_before_pixels ensures this is metadata validation, not image analysis.
    dataset = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=HEADER_TAGS)
    return {
        "study_instance_uid": str(dataset.get("StudyInstanceUID", "")),
        "series_instance_uid": str(dataset.get("SeriesInstanceUID", "")),
        "modality": str(dataset.get("Modality", "")),
    }


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(Path.cwd().resolve()).as_posix()


def validate_paths_under_raw_dir(entries: list[tuple[str, Path]], raw_dir: Path) -> None:
    raw_root = raw_dir.resolve()
    for _, relative_path in entries:
        resolved = relative_path.resolve()
        if raw_root != resolved and raw_root not in resolved.parents:
            raise RuntimeError(f"Checksum entry is outside the selected raw subset: {relative_path}")


def validate_subset(args: argparse.Namespace) -> dict[str, Any]:
    if not args.raw_dir.exists():
        raise RuntimeError(f"Raw subset directory does not exist: {args.raw_dir}")
    if not args.checksums.exists():
        raise RuntimeError(f"Checksum file does not exist: {args.checksums}")

    entries = read_checksum_manifest(args.checksums)
    validate_paths_under_raw_dir(entries, args.raw_dir)

    if len(entries) != EXPECTED_TOTAL_FILES:
        raise RuntimeError(f"Checksum manifest lists {len(entries)} files, expected {EXPECTED_TOTAL_FILES}.")

    local_files = sorted(path for path in args.raw_dir.rglob("*") if path.is_file())
    if len(local_files) != EXPECTED_TOTAL_FILES:
        raise RuntimeError(f"Raw subset contains {len(local_files)} files, expected {EXPECTED_TOTAL_FILES}.")

    listed_paths = {path for _, path in entries}
    local_relative_paths = {Path(relative_to_repo(path)) for path in local_files}
    unexpected_files = sorted(local_relative_paths - listed_paths)
    missing_from_directory = sorted(listed_paths - local_relative_paths)
    if unexpected_files or missing_from_directory:
        raise RuntimeError(
            "Raw subset files do not match checksum manifest: "
            f"{len(unexpected_files)} unexpected, {len(missing_from_directory)} missing."
        )

    series_counts = {series.series_instance_uid: 0 for series in EXPECTED_SERIES}
    modality_counts = {series.modality: 0 for series in EXPECTED_SERIES}
    first_files: dict[str, str] = {}
    last_files: dict[str, str] = {}

    for expected_digest, relative_path in entries:
        if not relative_path.exists():
            raise RuntimeError(f"Listed file does not exist: {relative_path}")
        actual_digest = sha256_file(relative_path)
        if actual_digest != expected_digest:
            raise RuntimeError(f"Checksum mismatch for {relative_path}")
        if not is_dicom_preamble(relative_path):
            raise RuntimeError(f"File does not have a DICOM preamble: {relative_path}")

        try:
            header = read_header(relative_path)
        except InvalidDicomError as exc:
            raise RuntimeError(f"Invalid DICOM file: {relative_path}") from exc

        if header["study_instance_uid"] != STUDY_INSTANCE_UID:
            raise RuntimeError(f"Unexpected StudyInstanceUID in {relative_path}")

        expected_series = EXPECTED_BY_SERIES_UID.get(header["series_instance_uid"])
        if expected_series is None:
            raise RuntimeError(f"Unexpected SeriesInstanceUID in {relative_path}: {header['series_instance_uid']}")
        if header["modality"] != expected_series.modality:
            raise RuntimeError(f"Unexpected Modality in {relative_path}: {header['modality']}")

        series_counts[expected_series.series_instance_uid] += 1
        modality_counts[expected_series.modality] += 1
        first_files.setdefault(expected_series.series_instance_uid, relative_path.as_posix())
        last_files[expected_series.series_instance_uid] = relative_path.as_posix()

    for series in EXPECTED_SERIES:
        actual_count = series_counts[series.series_instance_uid]
        if actual_count != series.expected_files:
            raise RuntimeError(
                f"{series.modality} series count is {actual_count}, expected {series.expected_files}."
            )

    summary: dict[str, Any] = {
        "collection": COLLECTION,
        "subject_id": SUBJECT_ID,
        "study_instance_uid": STUDY_INSTANCE_UID,
        "raw_subset_directory": relative_to_repo(args.raw_dir),
        "checksum_file": relative_to_repo(args.checksums),
        "summary_status": "passed",
        "local_only": True,
        "network_calls_performed": False,
        "pixel_data_read": False,
        "image_analysis_performed": False,
        "validated_total_files": EXPECTED_TOTAL_FILES,
        "checksum_entries_validated": len(entries),
        "series": [
            {
                "modality": series.modality,
                "series_instance_uid": series.series_instance_uid,
                "expected_files": series.expected_files,
                "validated_files": series_counts[series.series_instance_uid],
                "first_file": first_files[series.series_instance_uid],
                "last_file": last_files[series.series_instance_uid],
            }
            for series in EXPECTED_SERIES
        ],
        "modality_counts": modality_counts,
        "checks": {
            "all_listed_files_exist": True,
            "checksums_match": True,
            "dicom_preamble_present": True,
            "dicom_headers_read_without_pixel_data": True,
            "study_instance_uid_matches": True,
            "series_instance_uid_matches_selected_subset": True,
            "modality_matches_selected_series": True,
            "expected_counts_match": True,
        },
    }
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    args = parse_args()
    try:
        summary = validate_subset(args)
    except (OSError, RuntimeError, InvalidDicomError) as exc:
        print(f"Local DICOM subset validation failed: {exc}", file=sys.stderr)
        return 1

    print("Local DICOM subset validation passed.")
    print(f"Validated files: {summary['validated_total_files']}")
    for series in summary["series"]:
        print(
            f"{series['modality']} {series['series_instance_uid']}: "
            f"{series['validated_files']} files"
        )
    print(f"Summary: {relative_to_repo(args.summary_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
