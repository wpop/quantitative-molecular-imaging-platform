#!/usr/bin/env python3
"""Run a private SciPy operation on DB-selected local DICOM pixels."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import django
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import DatabaseError


DEFAULT_SETTINGS_MODULE = "config.settings.development"
OPERATION_CHOICES = ("rescale", "gaussian", "sobel")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a private scientific operation on one local DICOM slice selected "
            "through PostgreSQL metadata."
        ),
    )
    parser.add_argument(
        "--series-instance-uid",
        required=True,
        help="SeriesInstanceUID to select from PostgreSQL.",
    )
    parser.add_argument(
        "--operation",
        required=True,
        choices=OPERATION_CHOICES,
        help="Scientific operation to run.",
    )
    parser.add_argument(
        "--slice-index",
        type=int,
        default=None,
        help="Optional zero-based slice index. If omitted, the middle available slice is used.",
    )
    parser.add_argument(
        "--gaussian-sigma",
        type=float,
        default=1.0,
        help="Sigma for the Gaussian operation.",
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_MODULE,
        help="Django settings module.",
    )
    return parser.parse_args()


def setup_django(settings_module: str) -> None:
    backend_path = Path.cwd() / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


def format_optional_float(value: float | None) -> str:
    return "not applicable" if value is None else str(value)


def main() -> int:
    args = parse_args()
    try:
        setup_django(args.settings)
    except (ImproperlyConfigured, OSError) as exc:
        print(f"Scientific DICOM operation failed: {exc}", file=sys.stderr)
        return 1

    try:
        from apps.analysis.imaging_io import DicomPixelLoadError
        from apps.analysis.scientific_operations import (
            ScientificOperationError,
            run_scientific_operation_for_series,
        )

        result = run_scientific_operation_for_series(
            series_instance_uid=args.series_instance_uid,
            operation=args.operation,
            slice_index=args.slice_index,
            gaussian_sigma=args.gaussian_sigma,
            repo_root=Path.cwd(),
        )
    except (
        DicomPixelLoadError,
        ScientificOperationError,
        DatabaseError,
        ImproperlyConfigured,
        OSError,
    ) as exc:
        print(f"Scientific DICOM operation failed: {exc}", file=sys.stderr)
        return 1

    print("Scientific DICOM operation")
    print(f"Operation: {result.operation.value}")
    print(f"StudyInstanceUID: {result.study_instance_uid}")
    print(f"SeriesInstanceUID: {result.series_instance_uid}")
    print(f"SOPInstanceUID: {result.sop_instance_uid}")
    print(f"Database instance id: {result.instance_id}")
    print(f"Modality: {result.modality}")
    print(f"Selected slice index: {result.slice_index}")
    print(f"Available slices: {result.series_instance_count}")
    print(f"Rows: {result.rows}")
    print(f"Columns: {result.columns}")
    print(f"Source dtype: {result.source_dtype}")
    print(f"Result dtype: {result.result_dtype}")
    print(f"Value units: {result.value_units}")
    print(f"Gaussian sigma: {format_optional_float(result.gaussian_sigma)}")
    print(f"Source minimum: {result.source_minimum}")
    print(f"Source maximum: {result.source_maximum}")
    print(f"Source mean: {result.source_mean}")
    print(f"Result minimum: {result.result_minimum}")
    print(f"Result maximum: {result.result_maximum}")
    print(f"Result mean: {result.result_mean}")
    print(f"Result standard deviation: {result.result_standard_deviation}")
    print(f"Result shape: {result.result_array.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
