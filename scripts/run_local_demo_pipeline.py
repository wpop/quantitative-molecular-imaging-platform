#!/usr/bin/env python3
"""Run the local metadata-only backend demo pipeline.

This script orchestrates existing local workflow scripts. It validates the
already downloaded local DICOM subset, ingests DICOM header metadata into
PostgreSQL, runs the metadata-only series geometry summary, and prints a compact
database summary. It does not download data, call external services, read pixel
arrays, or perform image analysis.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import django


DEFAULT_SETTINGS_MODULE = "config.settings.development"
REPO_ROOT_MARKERS = ("backend", "scripts", "pyproject.toml")


@dataclass(frozen=True)
class DatabaseSummary:
    """Compact summary of metadata already stored in PostgreSQL."""

    studies_count: int
    series_count: int
    instances_count: int
    analysis_runs_count: int
    measurement_results_count: int
    modalities: list[str]
    latest_ingestion_job_status: str | None
    latest_analysis_run_status: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the local demo pipeline: validate local DICOM headers, ingest "
            "metadata, run the metadata-only geometry summary, and print final "
            "database counts. No data is downloaded."
        ),
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_MODULE,
        help="Django settings module passed to metadata ingestion and analysis steps.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip local checksum and DICOM header validation.",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip local DICOM header metadata ingestion.",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip the metadata-only series geometry summary.",
    )
    return parser.parse_args()


def ensure_repo_root() -> Path:
    repo_root = Path.cwd()
    missing = [marker for marker in REPO_ROOT_MARKERS if not (repo_root / marker).exists()]
    if missing:
        raise RuntimeError(
            "Run this script from the repository root. Missing expected paths: "
            + ", ".join(missing)
        )
    return repo_root


def print_section(title: str) -> None:
    print(flush=True)
    print(f"== {title} ==", flush=True)


def run_step(title: str, command: list[str]) -> None:
    print_section(title)
    print(" ".join(command), flush=True)
    subprocess.run(command, check=True)


def setup_django(settings_module: str, repo_root: Path) -> None:
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


def get_database_summary() -> DatabaseSummary:
    from apps.analysis.models import AnalysisRun, MeasurementResult
    from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy
    from apps.ingestion.models import IngestionJob

    latest_ingestion_job = IngestionJob.objects.order_by("-created_at", "-id").first()
    latest_analysis_run = AnalysisRun.objects.order_by("-created_at", "-id").first()
    modalities = list(
        ImagingSeries.objects.exclude(modality="")
        .order_by("modality")
        .values_list("modality", flat=True)
        .distinct(),
    )
    return DatabaseSummary(
        studies_count=ImagingStudy.objects.count(),
        series_count=ImagingSeries.objects.count(),
        instances_count=ImagingInstance.objects.count(),
        analysis_runs_count=AnalysisRun.objects.count(),
        measurement_results_count=MeasurementResult.objects.count(),
        modalities=modalities,
        latest_ingestion_job_status=latest_ingestion_job.status if latest_ingestion_job else None,
        latest_analysis_run_status=latest_analysis_run.status if latest_analysis_run else None,
    )


def format_optional(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value)


def print_database_summary(summary: DatabaseSummary) -> None:
    print_section("Final database summary")
    print(f"Studies: {summary.studies_count}")
    print(f"Series: {summary.series_count}")
    print(f"Instances: {summary.instances_count}")
    print(f"Analysis runs: {summary.analysis_runs_count}")
    print(f"Measurement results: {summary.measurement_results_count}")
    print(f"Modalities: {format_optional(summary.modalities)}")
    print(f"Latest ingestion job status: {format_optional(summary.latest_ingestion_job_status)}")
    print(f"Latest analysis run status: {format_optional(summary.latest_analysis_run_status)}")


def main() -> int:
    args = parse_args()
    try:
        repo_root = ensure_repo_root()
        if not args.skip_validation:
            run_step(
                "Validate local DICOM subset",
                [sys.executable, "scripts/validate_local_dicom_subset.py"],
            )
        if not args.skip_ingestion:
            run_step(
                "Ingest local DICOM metadata",
                [
                    sys.executable,
                    "scripts/ingest_local_dicom_metadata.py",
                    "--settings",
                    args.settings,
                ],
            )
        if not args.skip_analysis:
            run_step(
                "Run series geometry summary",
                [
                    sys.executable,
                    "scripts/run_series_geometry_summary.py",
                    "--settings",
                    args.settings,
                ],
            )
        setup_django(args.settings, repo_root)
        print_database_summary(get_database_summary())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Local demo pipeline failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
