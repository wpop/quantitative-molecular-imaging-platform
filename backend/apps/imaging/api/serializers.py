"""Serializers for read-only imaging metadata APIs."""

from rest_framework import serializers

from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy


class ImagingStudySerializer(serializers.ModelSerializer[ImagingStudy]):
    """Expose study-level metadata stored in PostgreSQL."""

    series_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ImagingStudy
        fields = (
            "id",
            "study_instance_uid",
            "accession_number",
            "study_description",
            "modality_summary",
            "study_date",
            "source_dataset",
            "source_subject_id",
            "series_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ImagingSeriesSerializer(serializers.ModelSerializer[ImagingSeries]):
    """Expose series-level metadata without raw DICOM content."""

    study_instance_uid = serializers.CharField(source="study.study_instance_uid", read_only=True)
    source_dataset = serializers.CharField(source="study.source_dataset", read_only=True)
    source_subject_id = serializers.CharField(source="study.source_subject_id", read_only=True)

    class Meta:
        model = ImagingSeries
        fields = (
            "id",
            "study",
            "study_instance_uid",
            "series_instance_uid",
            "modality",
            "series_description",
            "body_part_examined",
            "image_orientation_patient",
            "image_position_patient",
            "pixel_spacing",
            "slice_thickness",
            "number_of_instances",
            "source_dataset",
            "source_subject_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ImagingInstanceSerializer(serializers.ModelSerializer[ImagingInstance]):
    """Expose instance-level header metadata and checksum provenance."""

    series_instance_uid = serializers.CharField(source="series.series_instance_uid", read_only=True)
    study_instance_uid = serializers.CharField(
        source="series.study.study_instance_uid",
        read_only=True,
    )
    modality = serializers.CharField(source="series.modality", read_only=True)
    source_dataset = serializers.CharField(source="series.study.source_dataset", read_only=True)
    source_subject_id = serializers.CharField(
        source="series.study.source_subject_id",
        read_only=True,
    )

    class Meta:
        model = ImagingInstance
        fields = (
            "id",
            "series",
            "series_instance_uid",
            "study_instance_uid",
            "modality",
            "sop_instance_uid",
            "sop_class_uid",
            "instance_number",
            "rows",
            "columns",
            "file_sha256",
            "orthanc_instance_id",
            "source_dataset",
            "source_subject_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
