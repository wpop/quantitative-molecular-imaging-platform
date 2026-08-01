"""Metadata-only quantitative analysis services."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.analysis.models import AnalysisRun, MeasurementResult
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy

ALGORITHM_NAME = "series_geometry_summary"
ALGORITHM_VERSION = "0.1.0"
PIXEL_SPACING_COMPONENTS = 2


@dataclass(frozen=True)
class SeriesGeometrySummary:
    """Compact geometry values derived from PostgreSQL metadata only."""

    series_instance_uid: str
    modality: str
    number_of_instances: int
    rows: int | None
    columns: int | None
    pixel_spacing: list[float] | None
    slice_thickness: Decimal | None
    approximate_in_plane_width_mm: Decimal | None
    approximate_in_plane_height_mm: Decimal | None


@dataclass(frozen=True)
class GeometryAnalysisSummary:
    """Summary of one metadata-only geometry analysis run."""

    analysis_run_id: int
    study_instance_uid: str
    series_analyzed: int
    measurement_results_created: int
    series: list[SeriesGeometrySummary]


def decimal_from_float(value: float) -> Decimal:
    """Convert a float to a stored decimal value without binary artifacts."""
    return Decimal(str(value)).quantize(Decimal("0.00000001"))


def decimal_from_int(value: int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.00000001"))


def first_instance_for_series(series: ImagingSeries) -> ImagingInstance | None:
    return (
        series.instances.order_by("instance_number", "sop_instance_uid")
        .only("rows", "columns", "instance_number", "sop_instance_uid")
        .first()
    )


def compute_series_geometry(series: ImagingSeries) -> SeriesGeometrySummary:
    """Compute geometry summary from database metadata, not DICOM files."""
    first_instance = first_instance_for_series(series)
    rows = first_instance.rows if first_instance else None
    columns = first_instance.columns if first_instance else None
    pixel_spacing = series.pixel_spacing if isinstance(series.pixel_spacing, list) else None
    width_mm = None
    height_mm = None

    if (
        rows is not None
        and columns is not None
        and pixel_spacing
        and len(pixel_spacing) >= PIXEL_SPACING_COMPONENTS
    ):
        row_spacing = float(pixel_spacing[0])
        column_spacing = float(pixel_spacing[1])
        width_mm = decimal_from_float(columns * column_spacing)
        height_mm = decimal_from_float(rows * row_spacing)

    return SeriesGeometrySummary(
        series_instance_uid=series.series_instance_uid,
        modality=series.modality,
        number_of_instances=series.number_of_instances,
        rows=rows,
        columns=columns,
        pixel_spacing=[float(value) for value in pixel_spacing] if pixel_spacing else None,
        slice_thickness=series.slice_thickness,
        approximate_in_plane_width_mm=width_mm,
        approximate_in_plane_height_mm=height_mm,
    )


def measurement_metadata(summary: SeriesGeometrySummary) -> dict[str, Any]:
    return {
        "series_instance_uid": summary.series_instance_uid,
        "modality": summary.modality,
        "metadata_only": True,
        "dicom_files_read": False,
        "pixel_data_read": False,
    }


def measurement_rows(summary: SeriesGeometrySummary) -> list[tuple[str, Decimal, str]]:
    rows: list[tuple[str, Decimal, str]] = [
        ("number_of_instances", decimal_from_int(summary.number_of_instances), "count"),
    ]
    if summary.rows is not None:
        rows.append(("rows", decimal_from_int(summary.rows), "pixels"))
    if summary.columns is not None:
        rows.append(("columns", decimal_from_int(summary.columns), "pixels"))
    if summary.pixel_spacing and len(summary.pixel_spacing) >= PIXEL_SPACING_COMPONENTS:
        rows.append(("pixel_spacing_row", decimal_from_float(summary.pixel_spacing[0]), "mm"))
        rows.append(("pixel_spacing_column", decimal_from_float(summary.pixel_spacing[1]), "mm"))
    if summary.slice_thickness is not None:
        rows.append(("slice_thickness", summary.slice_thickness, "mm"))
    if summary.approximate_in_plane_width_mm is not None:
        rows.append(("approximate_in_plane_width", summary.approximate_in_plane_width_mm, "mm"))
    if summary.approximate_in_plane_height_mm is not None:
        rows.append(("approximate_in_plane_height", summary.approximate_in_plane_height_mm, "mm"))
    return rows


def summary_to_json(summary: GeometryAnalysisSummary) -> dict[str, Any]:
    return {
        "analysis_run_id": summary.analysis_run_id,
        "study_instance_uid": summary.study_instance_uid,
        "series_analyzed": summary.series_analyzed,
        "measurement_results_created": summary.measurement_results_created,
        "metadata_only": True,
        "dicom_files_read": False,
        "pixel_data_read": False,
        "image_analysis_performed": False,
        "series": [
            {
                "series_instance_uid": series.series_instance_uid,
                "modality": series.modality,
                "number_of_instances": series.number_of_instances,
                "rows": series.rows,
                "columns": series.columns,
                "pixel_spacing": series.pixel_spacing,
                "slice_thickness": str(series.slice_thickness)
                if series.slice_thickness is not None
                else None,
                "approximate_in_plane_width_mm": str(series.approximate_in_plane_width_mm)
                if series.approximate_in_plane_width_mm is not None
                else None,
                "approximate_in_plane_height_mm": str(series.approximate_in_plane_height_mm)
                if series.approximate_in_plane_height_mm is not None
                else None,
            }
            for series in summary.series
        ],
    }


def run_series_geometry_summary() -> GeometryAnalysisSummary:
    """Create a metadata-only geometry analysis run from ingested ORM records."""
    if not ImagingStudy.objects.exists():
        message = "No imaging studies are available for geometry summary."
        raise RuntimeError(message)
    if not ImagingSeries.objects.exists():
        message = "No imaging series are available for geometry summary."
        raise RuntimeError(message)
    if not ImagingInstance.objects.exists():
        message = "No imaging instances are available for geometry summary."
        raise RuntimeError(message)

    study = ImagingStudy.objects.order_by("study_instance_uid").first()
    if study is None:
        message = "No imaging study could be selected for the analysis run."
        raise RuntimeError(message)

    series_records = list(
        ImagingSeries.objects.select_related("study").order_by(
            "study__study_instance_uid",
            "modality",
            "series_instance_uid",
        ),
    )
    series_summaries = [compute_series_geometry(series) for series in series_records]

    with transaction.atomic():
        analysis_run = AnalysisRun.objects.create(
            study=study,
            status=AnalysisRun.Status.RUNNING,
            name="Series geometry summary",
            algorithm_name=ALGORITHM_NAME,
            algorithm_version=ALGORITHM_VERSION,
            parameters={
                "metadata_only": True,
                "dicom_files_read": False,
                "pixel_data_read": False,
                "series_count": len(series_summaries),
            },
            started_at=timezone.now(),
        )
        measurement_count = 0
        for series_summary in series_summaries:
            metadata = measurement_metadata(series_summary)
            for name, value, unit in measurement_rows(series_summary):
                MeasurementResult.objects.create(
                    analysis_run=analysis_run,
                    name=name,
                    value=value,
                    unit=unit,
                    region_label=series_summary.series_instance_uid,
                    metadata=metadata,
                )
                measurement_count += 1

        db_count = MeasurementResult.objects.filter(analysis_run=analysis_run).count()
        if db_count != measurement_count:
            message = (
                f"Database validation failed: created {measurement_count} measurements "
                f"but found {db_count}."
            )
            raise RuntimeError(message)

        analysis_run.status = AnalysisRun.Status.COMPLETED
        analysis_run.completed_at = timezone.now()
        analysis_run.save(update_fields=["status", "completed_at", "updated_at"])

    return GeometryAnalysisSummary(
        analysis_run_id=analysis_run.id,
        study_instance_uid=study.study_instance_uid,
        series_analyzed=len(series_summaries),
        measurement_results_created=measurement_count,
        series=series_summaries,
    )
