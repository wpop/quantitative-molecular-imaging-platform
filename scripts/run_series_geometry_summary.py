#!/usr/bin/env python3
"""Run a metadata-only quantitative geometry summary.

This script reads PostgreSQL metadata only. It never reads raw DICOM files,
pixel arrays, or performs image analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import django
from django.core.exceptions import ImproperlyConfigured


DEFAULT_SETTINGS_MODULE = "config.settings.development"
SUMMARY_PATH = Path("backend/tests/real_data/metadata_candidates/series_geometry_summary.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute a metadata-only series geometry summary from already "
            "ingested PostgreSQL metadata."
        ),
    )
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_MODULE,
        help="Django settings module.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=SUMMARY_PATH,
        help="Output JSON summary path.",
    )
    return parser.parse_args()


def setup_django(settings_module: str) -> None:
    backend_path = Path.cwd() / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    django.setup()


def main() -> int:
    args = parse_args()
    try:
        setup_django(args.settings)
        from apps.analysis.services import run_series_geometry_summary, summary_to_json

        summary = run_series_geometry_summary()
        payload = summary_to_json(summary)
        args.summary_path.parent.mkdir(parents=True, exist_ok=True)
        args.summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except (OSError, RuntimeError, ImproperlyConfigured) as exc:
        print(f"Series geometry summary failed: {exc}", file=sys.stderr)
        return 1

    print(f"Analysis run id: {summary.analysis_run_id}")
    print(f"Series analyzed: {summary.series_analyzed}")
    print(f"Measurement results created: {summary.measurement_results_created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
