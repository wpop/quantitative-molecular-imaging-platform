#!/usr/bin/env python3
"""Generate a local PNG visualization for DB-selected DICOM pixels."""

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
            "Generate a local PNG visualization from a scientific operation on "
            "one DICOM slice selected through PostgreSQL metadata."
        ),
    )
    parser.add_argument("--series-instance-uid", required=True)
    parser.add_argument("--operation", required=True, choices=OPERATION_CHOICES)
    parser.add_argument("--slice-index", type=int, default=None)
    parser.add_argument("--gaussian-sigma", type=float, default=1.0)
    parser.add_argument("--window-center", type=float, default=None)
    parser.add_argument("--window-width", type=float, default=None)
    parser.add_argument("--lower-percentile", type=float, default=1.0)
    parser.add_argument("--upper-percentile", type=float, default=99.0)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/visualizations"))
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_MODULE)
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
        print(f"DICOM visualization generation failed: {exc}", file=sys.stderr)
        return 1

    try:
        from apps.analysis.artifact_registry import (
            VisualizationArtifactRegistryError,
            register_visualization_artifact,
        )
        from apps.analysis.imaging_io import DicomPixelLoadError
        from apps.analysis.scientific_operations import ScientificOperationError
        from apps.analysis.visualization import VisualizationError, run_visualization_for_series

        artifact = run_visualization_for_series(
            series_instance_uid=args.series_instance_uid,
            operation=args.operation,
            output_root=args.output_root,
            repo_root=Path.cwd(),
            slice_index=args.slice_index,
            gaussian_sigma=args.gaussian_sigma,
            window_center=args.window_center,
            window_width=args.window_width,
            lower_percentile=args.lower_percentile,
            upper_percentile=args.upper_percentile,
            dpi=args.dpi,
        )
        registered_artifact = register_visualization_artifact(artifact)
    except (
        VisualizationArtifactRegistryError,
        VisualizationError,
        ScientificOperationError,
        DicomPixelLoadError,
        DatabaseError,
        ImproperlyConfigured,
        OSError,
    ) as exc:
        print(f"DICOM visualization generation failed: {exc}", file=sys.stderr)
        return 1

    print("DICOM visualization artifact")
    print(f"Operation: {artifact.operation.value}")
    print(f"Modality: {artifact.modality}")
    print(f"Slice index: {artifact.slice_index}")
    print(f"Rows: {artifact.rows}")
    print(f"Columns: {artifact.columns}")
    print(f"Value units: {artifact.value_units}")
    print(f"Colormap: {artifact.colormap}")
    print(f"Display minimum: {artifact.display_minimum}")
    print(f"Display maximum: {artifact.display_maximum}")
    print(f"Window center: {format_optional_float(artifact.window_center)}")
    print(f"Window width: {format_optional_float(artifact.window_width)}")
    print(f"Relative artifact path: {artifact.relative_png_path}")
    print(f"MIME type: {artifact.mime_type}")
    print(f"File size bytes: {artifact.file_size_bytes}")
    print(f"SHA-256: {artifact.sha256}")
    print(f"Artifact database id: {registered_artifact.id}")
    print("Artifact registered: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
