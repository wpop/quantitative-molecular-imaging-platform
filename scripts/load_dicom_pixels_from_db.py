#!/usr/bin/env python3
"""Load one DB-selected local DICOM pixel array for scientific inspection."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import django
import numpy as np
from django.core.exceptions import ImproperlyConfigured


DEFAULT_SETTINGS_MODULE = "config.settings.development"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load one local DICOM pixel array selected through PostgreSQL metadata.",
    )
    parser.add_argument(
        "--series-instance-uid",
        required=True,
        help="SeriesInstanceUID to select from PostgreSQL.",
    )
    parser.add_argument(
        "--slice-index",
        type=int,
        default=None,
        help="Optional zero-based slice index. If omitted, the middle available slice is used.",
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_MODULE,
        help="Django settings module.",
    )
    return parser.parse_args()


def setup_django(settings_module: str) -> None:
    repo_root = Path.cwd()
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


def main() -> int:
    args = parse_args()
    try:
        setup_django(args.settings)
        from apps.analysis.imaging_io import DicomPixelLoadError, load_dicom_pixels_for_series

        loaded = load_dicom_pixels_for_series(
            series_instance_uid=args.series_instance_uid,
            slice_index=args.slice_index,
            repo_root=Path.cwd(),
        )
    except (DicomPixelLoadError, ImproperlyConfigured, OSError) as exc:
        print(f"DICOM pixel loading failed: {exc}", file=sys.stderr)
        return 1

    pixel_array = loaded.pixel_array
    print("Selected DICOM pixels")
    print(f"StudyInstanceUID: {loaded.study_instance_uid}")
    print(f"SeriesInstanceUID: {loaded.series_instance_uid}")
    print(f"SOPInstanceUID: {loaded.sop_instance_uid}")
    print(f"Database instance id: {loaded.instance_id}")
    print(f"Modality: {loaded.modality}")
    print(f"Selected slice index: {loaded.slice_index}")
    print(f"Available slices: {loaded.series_instance_count}")
    print(f"Rows: {loaded.rows}")
    print(f"Columns: {loaded.columns}")
    print(f"Array shape: {pixel_array.shape[0]} x {pixel_array.shape[1]}")
    print(f"NumPy dtype: {loaded.numpy_dtype}")
    print(f"Raw pixel minimum: {np.min(pixel_array)}")
    print(f"Raw pixel maximum: {np.max(pixel_array)}")
    print(f"Raw pixel mean: {float(np.mean(pixel_array)):.6f}")
    print(f"Rescale slope: {loaded.rescale_slope}")
    print(f"Rescale intercept: {loaded.rescale_intercept}")
    print(f"Pixel spacing: {loaded.pixel_spacing}")
    print(f"Slice thickness: {loaded.slice_thickness}")
    print(f"Photometric interpretation: {loaded.photometric_interpretation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
