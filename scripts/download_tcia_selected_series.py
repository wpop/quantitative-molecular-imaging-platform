#!/usr/bin/env python3
"""Download the approved TCIA/NBIA CT and PT series to a local raw-data path.

This utility downloads only the two selected SeriesInstanceUID values. Raw DICOM
files are local-only validation data and must remain outside Git-tracked source
files under datasets/raw/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
COLLECTION = "CT-vs-PET-Ventilation-Imaging"
SUBJECT_ID = "CT-PET-VI-01"
STUDY_INSTANCE_UID = "1.3.6.1.4.1.14519.5.2.1.297577087050970310787702792940607009472"
RAW_OUTPUT_DIR = Path("datasets/raw/tcia") / COLLECTION / SUBJECT_ID
CHECKSUM_PATH = Path("backend/tests/real_data/checksums.sha256")
SUMMARY_PATH = Path("backend/tests/real_data/metadata_candidates/downloaded_subset_summary.json")
BUFFER_SIZE = 1024 * 1024
EXPECTED_TOTAL_OBJECTS = 1149
EXPECTED_TOTAL_BYTES = 574176008


@dataclass(frozen=True)
class SelectedSeries:
    modality: str
    series_instance_uid: str
    expected_objects: int
    expected_size_bytes: int

    @property
    def directory_name(self) -> str:
        return f"{self.modality}_{self.series_instance_uid}"


SELECTED_SERIES = (
    SelectedSeries(
        modality="CT",
        series_instance_uid="1.3.6.1.4.1.14519.5.2.1.133320994602881796006698916833783151254",
        expected_objects=990,
        expected_size_bytes=522654776,
    ),
    SelectedSeries(
        modality="PT",
        series_instance_uid="1.3.6.1.4.1.14519.5.2.1.246352124462042526540512717085218914533",
        expected_objects=159,
        expected_size_bytes=51521232,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download only the approved CT and PT SeriesInstanceUID values for "
            "local validation. Collection, patient, and study downloads are not supported."
        )
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Public NBIA Search REST API base URL.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RAW_OUTPUT_DIR,
        help="Local raw DICOM output directory outside Git-tracked source files.",
    )
    parser.add_argument(
        "--checksum-path",
        type=Path,
        default=CHECKSUM_PATH,
        help="Local SHA-256 checksum file for the selected extracted DICOM files.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=SUMMARY_PATH,
        help="Local JSON summary for the selected subset download.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="HTTP timeout for each selected series ZIP download.",
    )
    return parser.parse_args()


def get_image_url(base_url: str, series_instance_uid: str) -> str:
    params = urlencode({"SeriesInstanceUID": series_instance_uid})
    return f"{base_url.rstrip('/')}/getImage?{params}"


def copy_response_to_file(response: BinaryIO, destination: Path) -> int:
    total_bytes = 0
    with destination.open("wb") as output:
        while True:
            chunk = response.read(BUFFER_SIZE)
            if not chunk:
                break
            output.write(chunk)
            total_bytes += len(chunk)
    return total_bytes


def download_series_zip(series: SelectedSeries, base_url: str, timeout_seconds: int, temp_dir: Path) -> tuple[Path, int]:
    zip_path = temp_dir / f"{series.modality}_{series.series_instance_uid}.zip"
    url = get_image_url(base_url, series.series_instance_uid)
    with urlopen(url, timeout=timeout_seconds) as response:
        downloaded_bytes = copy_response_to_file(response, zip_path)
    return zip_path, downloaded_bytes


def safe_extract_zip(zip_path: Path, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    extracted_files: list[Path] = []

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = destination / member.filename
            resolved_member_path = member_path.resolve()
            if destination_root != resolved_member_path and destination_root not in resolved_member_path.parents:
                raise RuntimeError(f"Blocked unsafe ZIP member path: {member.filename}")

            if member.is_dir():
                resolved_member_path.mkdir(parents=True, exist_ok=True)
                continue

            resolved_member_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, resolved_member_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=BUFFER_SIZE)
            extracted_files.append(resolved_member_path)

    return extracted_files


def is_dicom_file(path: Path) -> bool:
    with path.open("rb") as handle:
        header = handle.read(132)
    return len(header) >= 132 and header[128:132] == b"DICM"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(BUFFER_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def remove_empty_directories(root: Path) -> None:
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(Path.cwd().resolve()).as_posix()


def write_checksums(checksum_path: Path, checksums: list[tuple[str, str]]) -> None:
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SHA-256 checksums for the local selected TCIA/NBIA DICOM subset.",
        "# Raw DICOM files are stored outside Git under datasets/raw/.",
        "# Format:",
        "# <sha256>  <relative_path_to_dicom_file>",
        "",
    ]
    lines.extend(f"{digest}  {relative_path}" for digest, relative_path in checksums)
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(summary_path: Path, summary: dict[str, object]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_output_dir(output_dir: Path) -> None:
    output = output_dir.resolve()
    raw_root = (Path.cwd() / "datasets/raw").resolve()
    if raw_root != output and raw_root not in output.parents:
        raise RuntimeError(f"Output directory must be under {raw_root}")


def process_series(args: argparse.Namespace, series: SelectedSeries, temp_dir: Path) -> dict[str, object]:
    series_dir = args.output_dir / series.directory_name
    if series_dir.exists():
        raise RuntimeError(f"Output series directory already exists: {series_dir}")

    zip_path, downloaded_zip_bytes = download_series_zip(series, args.base_url, args.timeout_seconds, temp_dir)
    extracted_files = safe_extract_zip(zip_path, series_dir)
    dicom_files = sorted(path for path in extracted_files if is_dicom_file(path))
    non_dicom_files = sorted(path for path in extracted_files if path not in dicom_files)
    total_dicom_bytes = sum(path.stat().st_size for path in dicom_files)

    if len(dicom_files) != series.expected_objects:
        raise RuntimeError(
            f"{series.modality} extracted {len(dicom_files)} DICOM files, "
            f"expected {series.expected_objects}."
        )
    if total_dicom_bytes != series.expected_size_bytes:
        raise RuntimeError(
            f"{series.modality} extracted {total_dicom_bytes} DICOM bytes, "
            f"expected {series.expected_size_bytes}."
        )

    for path in non_dicom_files:
        path.unlink()
    remove_empty_directories(series_dir)

    return {
        "modality": series.modality,
        "series_instance_uid": series.series_instance_uid,
        "expected_objects": series.expected_objects,
        "expected_size_bytes": series.expected_size_bytes,
        "downloaded_zip_bytes": downloaded_zip_bytes,
        "extracted_dicom_count": len(dicom_files),
        "extracted_dicom_bytes": total_dicom_bytes,
        "removed_non_dicom_files": len(non_dicom_files),
        "output_directory": relative_to_repo(series_dir),
        "first_dicom_file": relative_to_repo(dicom_files[0]),
        "last_dicom_file": relative_to_repo(dicom_files[-1]),
        "_checksum_source_files": [relative_to_repo(path) for path in dicom_files],
    }


def main() -> int:
    args = parse_args()

    try:
        validate_output_dir(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)

        series_summaries: list[dict[str, object]] = []
        checksum_entries: list[tuple[str, str]] = []

        with tempfile.TemporaryDirectory(prefix="tcia_selected_series_") as temp_name:
            temp_dir = Path(temp_name)
            for series in SELECTED_SERIES:
                summary = process_series(args, series, temp_dir)
                series_summaries.append(summary)
                checksum_source_files = summary.pop("_checksum_source_files")
                if not isinstance(checksum_source_files, list):
                    raise RuntimeError("Internal checksum source list was not generated.")
                for relative_path in checksum_source_files:
                    path = Path(str(relative_path))
                    checksum_entries.append((sha256_file(path), path.as_posix()))

        checksum_entries.sort(key=lambda item: item[1])
        write_checksums(args.checksum_path, checksum_entries)

        total_files = sum(int(summary["extracted_dicom_count"]) for summary in series_summaries)
        total_bytes = sum(int(summary["extracted_dicom_bytes"]) for summary in series_summaries)
        if total_files != EXPECTED_TOTAL_OBJECTS or total_bytes != EXPECTED_TOTAL_BYTES:
            raise RuntimeError(
                f"Selected subset totals were {total_files} files and {total_bytes} bytes; "
                f"expected {EXPECTED_TOTAL_OBJECTS} files and {EXPECTED_TOTAL_BYTES} bytes."
            )

        download_summary: dict[str, object] = {
            "collection": COLLECTION,
            "subject_id": SUBJECT_ID,
            "study_instance_uid": STUDY_INSTANCE_UID,
            "raw_dicom_stored_in_git": False,
            "full_collection_downloaded": False,
            "selected_series_only": True,
            "expected_total_objects": EXPECTED_TOTAL_OBJECTS,
            "expected_total_bytes": EXPECTED_TOTAL_BYTES,
            "extracted_total_dicom_files": total_files,
            "extracted_total_dicom_bytes": total_bytes,
            "output_directory": relative_to_repo(args.output_dir),
            "checksum_file": relative_to_repo(args.checksum_path),
            "series": series_summaries,
        }
        write_summary(args.summary_path, download_summary)

    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Selected subset download failed: {exc}", file=sys.stderr)
        return 1

    print(f"Downloaded selected DICOM files: {total_files}")
    print(f"Total extracted DICOM bytes: {total_bytes}")
    print(f"Output directory: {relative_to_repo(args.output_dir)}")
    print(f"Checksum file: {relative_to_repo(args.checksum_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
