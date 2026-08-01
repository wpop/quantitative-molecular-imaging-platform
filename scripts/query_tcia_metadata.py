#!/usr/bin/env python3
"""Query TCIA/NBIA metadata for a tiny real-data subset candidate.

This script uses public NBIA metadata endpoints only. It never calls image
download endpoints and never downloads DICOM image files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_BASE_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
DEFAULT_COLLECTION = "CT-vs-PET-Ventilation-Imaging"
DEFAULT_OUTPUT_DIR = Path("backend/tests/real_data/metadata_candidates")
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PATIENTS_TO_SCAN = 20
DEFAULT_MAX_STUDIES_PER_PATIENT = 5
MODALITY_PRIORITY = ("CT", "PT")


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class NbiaClient:
    """Small metadata-only NBIA client."""

    base_url: str
    timeout_seconds: int

    def get_json(self, endpoint: str, params: dict[str, str]) -> list[JsonObject]:
        """Fetch JSON from an NBIA metadata endpoint."""
        url = f"{self.base_url.rstrip('/')}/{endpoint}?{urlencode(params)}"
        with urlopen(url, timeout=self.timeout_seconds) as response:
            payload = response.read()
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, list):
            raise TypeError(f"Expected list response from {endpoint}, got {type(data).__name__}")
        return [item for item in data if isinstance(item, dict)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query public TCIA/NBIA collection, study, and series metadata for "
            "a tiny candidate subset. This does not download DICOM images."
        )
    )
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="TCIA/NBIA collection name.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for small metadata snapshots.",
    )
    parser.add_argument(
        "--max-series",
        type=int,
        default=2,
        choices=(1, 2),
        help="Maximum number of series to include in the tiny candidate subset.",
    )
    parser.add_argument(
        "--max-patients-to-scan",
        type=int,
        default=DEFAULT_MAX_PATIENTS_TO_SCAN,
        help="Safety limit for patient metadata records scanned while selecting a subset.",
    )
    parser.add_argument(
        "--max-studies-per-patient",
        type=int,
        default=DEFAULT_MAX_STUDIES_PER_PATIENT,
        help="Safety limit for study metadata records scanned per patient.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Public NBIA Search REST API base URL.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout for each metadata request.",
    )
    return parser.parse_args()


def json_key(record: JsonObject, *names: str) -> str:
    for name in names:
        value = record.get(name)
        if value is not None:
            return str(value)
    return ""


def safe_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return label or "unknown"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sorted_records(records: list[JsonObject], *keys: str) -> list[JsonObject]:
    return sorted(records, key=lambda record: tuple(json_key(record, key) for key in keys))


def choose_preferred_series(series_records: list[JsonObject], max_series: int) -> list[JsonObject]:
    ordered = sorted_records(series_records, "Modality", "SeriesInstanceUID", "SeriesNumber")
    chosen: list[JsonObject] = []

    for modality in MODALITY_PRIORITY:
        for record in ordered:
            if json_key(record, "Modality").upper() == modality and record not in chosen:
                chosen.append(record)
                break
        if len(chosen) >= max_series:
            return chosen

    for record in ordered:
        if record not in chosen:
            chosen.append(record)
        if len(chosen) >= max_series:
            break

    return chosen


def summarize_series_size(series_uid: str, raw_size_response: list[JsonObject]) -> JsonObject:
    size_record = raw_size_response[0] if raw_size_response else {}
    return {
        "series_instance_uid": series_uid,
        "object_count": size_record.get("ObjectCount", "PLACEHOLDER_OBJECT_COUNT_NOT_RETURNED"),
        "total_size_bytes": size_record.get("TotalSizeInBytes", "PLACEHOLDER_TOTAL_SIZE_NOT_RETURNED"),
        "raw_response": raw_size_response,
    }


def build_subset(
    *,
    collection: str,
    patient: JsonObject,
    study: JsonObject,
    series_records: list[JsonObject],
    series_sizes: list[JsonObject],
) -> JsonObject:
    return {
        "metadata_only": True,
        "dicom_files_downloaded": 0,
        "collection": collection,
        "selection_policy": (
            "Deterministic first suitable subject and study, preferring CT and PT series "
            "when both are available from metadata."
        ),
        "subject": {
            "patient_id": json_key(patient, "PatientId", "PatientID"),
            "collection": json_key(patient, "Collection"),
            "patient_sex": patient.get("PatientSex", "PLACEHOLDER_NOT_RETURNED"),
            "species_description": patient.get("SpeciesDescription", "PLACEHOLDER_NOT_RETURNED"),
        },
        "study": {
            "study_instance_uid": json_key(study, "StudyInstanceUID"),
            "study_description": study.get("StudyDescription", "PLACEHOLDER_NOT_RETURNED"),
            "study_date": study.get("StudyDate", "PLACEHOLDER_NOT_RETURNED"),
            "series_count": study.get("SeriesCount", "PLACEHOLDER_NOT_RETURNED"),
        },
        "series": [
            {
                "series_instance_uid": json_key(record, "SeriesInstanceUID"),
                "modality": record.get("Modality", "PLACEHOLDER_NOT_RETURNED"),
                "series_description": record.get("SeriesDescription", "PLACEHOLDER_NOT_RETURNED"),
                "body_part_examined": record.get("BodyPartExamined", "PLACEHOLDER_NOT_RETURNED"),
                "manufacturer": record.get("Manufacturer", "PLACEHOLDER_NOT_RETURNED"),
                "manufacturer_model_name": record.get("ManufacturerModelName", "PLACEHOLDER_NOT_RETURNED"),
            }
            for record in series_records
        ],
        "series_sizes": series_sizes,
        "notes": (
            "This file contains real public metadata only. It does not contain DICOM "
            "pixel data, local DICOM file paths, SOPInstanceUID lists, or checksums."
        ),
    }


def query_metadata(args: argparse.Namespace) -> JsonObject:
    client = NbiaClient(base_url=args.base_url, timeout_seconds=args.timeout_seconds)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    patients = sorted_records(
        client.get_json("getPatient", {"Collection": args.collection, "format": "json"}),
        "PatientId",
        "PatientID",
    )
    write_json(output_dir / "patients.json", patients)

    queried_studies: list[JsonObject] = []
    queried_series: list[JsonObject] = []
    series_size_snapshots: list[JsonObject] = []

    for patient_index, patient in enumerate(patients[: args.max_patients_to_scan], start=1):
        patient_id = json_key(patient, "PatientId", "PatientID")
        if not patient_id:
            continue

        studies = sorted_records(
            client.get_json(
                "getPatientStudy",
                {"Collection": args.collection, "PatientID": patient_id, "format": "json"},
            ),
            "StudyInstanceUID",
        )
        queried_studies.append({"patient_index": patient_index, "patient_id": patient_id, "response": studies})

        for study_index, study in enumerate(studies[: args.max_studies_per_patient], start=1):
            study_uid = json_key(study, "StudyInstanceUID")
            if not study_uid:
                continue

            series_records = sorted_records(
                client.get_json(
                    "getSeries",
                    {
                        "Collection": args.collection,
                        "PatientID": patient_id,
                        "StudyInstanceUID": study_uid,
                        "format": "json",
                    },
                ),
                "Modality",
                "SeriesInstanceUID",
            )
            queried_series.append(
                {
                    "patient_index": patient_index,
                    "study_index": study_index,
                    "patient_id": patient_id,
                    "study_instance_uid": study_uid,
                    "response": series_records,
                }
            )

            chosen_series = choose_preferred_series(series_records, args.max_series)
            chosen_modalities = {json_key(record, "Modality").upper() for record in chosen_series}
            if chosen_series and (len(chosen_series) == args.max_series or "CT" in chosen_modalities):
                for record in chosen_series:
                    series_uid = json_key(record, "SeriesInstanceUID")
                    if not series_uid:
                        continue
                    raw_size = client.get_json(
                        "getSeriesSize",
                        {"SeriesInstanceUID": series_uid, "format": "json"},
                    )
                    series_size_snapshots.append(summarize_series_size(series_uid, raw_size))

                write_json(output_dir / "queried_studies.json", queried_studies)
                write_json(output_dir / "queried_series.json", queried_series)
                write_json(output_dir / "selected_series_sizes.json", series_size_snapshots)
                subset = build_subset(
                    collection=args.collection,
                    patient=patient,
                    study=study,
                    series_records=chosen_series,
                    series_sizes=series_size_snapshots,
                )
                write_json(output_dir / "tiny_subset_candidate.json", subset)
                return subset

    write_json(output_dir / "queried_studies.json", queried_studies)
    write_json(output_dir / "queried_series.json", queried_series)
    raise RuntimeError(
        "No suitable metadata-only subset was found within the configured safety limits."
    )


def main() -> int:
    args = parse_args()
    if args.max_patients_to_scan < 1 or args.max_studies_per_patient < 1:
        print("Safety limits must be positive integers.", file=sys.stderr)
        return 2

    try:
        subset = query_metadata(args)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, RuntimeError, TypeError) as exc:
        print(f"Metadata query failed: {exc}", file=sys.stderr)
        print("No DICOM files were downloaded.", file=sys.stderr)
        return 1

    print(f"Wrote metadata-only tiny subset candidate for {subset['collection']}.")
    print(f"Selected subject: {subset['subject']['patient_id']}")
    print(f"Selected study: {subset['study']['study_instance_uid']}")
    print(f"Selected series count: {len(subset['series'])}")
    print("No DICOM files were downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
