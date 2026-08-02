"""Admin registrations for imaging domain models."""

from django.contrib import admin

from .models import ImagingInstance, ImagingSeries, ImagingStudy, LocalDicomFile


@admin.register(ImagingStudy)
class ImagingStudyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "study_instance_uid",
        "study_description",
        "modality_summary",
        "study_date",
        "source_dataset",
        "created_at",
    )
    list_filter = ("source_dataset", "study_date", "created_at")
    search_fields = (
        "study_instance_uid",
        "accession_number",
        "study_description",
        "source_dataset",
        "source_subject_id",
    )


@admin.register(ImagingSeries)
class ImagingSeriesAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "series_instance_uid",
        "study",
        "modality",
        "series_description",
        "body_part_examined",
        "number_of_instances",
    )
    list_filter = ("modality", "body_part_examined", "created_at")
    search_fields = (
        "series_instance_uid",
        "series_description",
        "study__study_instance_uid",
    )


@admin.register(ImagingInstance)
class ImagingInstanceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "sop_instance_uid",
        "series",
        "instance_number",
        "rows",
        "columns",
        "orthanc_instance_id",
    )
    list_filter = ("created_at",)
    search_fields = (
        "sop_instance_uid",
        "sop_class_uid",
        "file_sha256",
        "orthanc_instance_id",
        "series__series_instance_uid",
    )


@admin.register(LocalDicomFile)
class LocalDicomFileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "instance",
        "relative_path",
        "file_size_bytes",
        "is_available",
        "updated_at",
    )
    search_fields = (
        "instance__sop_instance_uid",
        "relative_path",
        "file_sha256",
    )
    list_filter = (
        "is_available",
        "created_at",
        "updated_at",
    )
