"""Domain models for deidentified imaging metadata."""

from django.db import models


class ImagingStudy(models.Model):
    """Represent one deidentified DICOM study from a public dataset."""

    study_instance_uid = models.CharField(max_length=64, unique=True)
    accession_number = models.CharField(max_length=64, blank=True)
    study_description = models.CharField(max_length=255, blank=True)
    modality_summary = models.CharField(max_length=128, blank=True)
    study_date = models.DateField(blank=True, null=True)
    source_dataset = models.CharField(max_length=128, blank=True)
    source_subject_id = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-study_date", "study_instance_uid")
        indexes = (
            models.Index(fields=["study_date"], name="imaging_study_date_idx"),
            models.Index(fields=["source_dataset"], name="imaging_study_source_idx"),
            models.Index(fields=["accession_number"], name="imaging_study_accession_idx"),
        )

    def __str__(self) -> str:
        return self.study_description or self.study_instance_uid


class ImagingSeries(models.Model):
    """Represent one DICOM series inside a study."""

    study = models.ForeignKey(
        ImagingStudy,
        related_name="series",
        on_delete=models.CASCADE,
    )
    series_instance_uid = models.CharField(max_length=64, unique=True)
    modality = models.CharField(max_length=16)
    series_description = models.CharField(max_length=255, blank=True)
    body_part_examined = models.CharField(max_length=64, blank=True)
    image_orientation_patient = models.JSONField(blank=True, null=True)
    image_position_patient = models.JSONField(blank=True, null=True)
    pixel_spacing = models.JSONField(blank=True, null=True)
    slice_thickness = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        blank=True,
        null=True,
    )
    number_of_instances = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("study_id", "modality", "series_instance_uid")
        indexes = (
            models.Index(fields=["study", "modality"], name="imaging_series_study_mod_idx"),
            models.Index(fields=["modality"], name="imaging_series_modality_idx"),
            models.Index(fields=["body_part_examined"], name="imaging_series_body_part_idx"),
        )

    def __str__(self) -> str:
        label = self.series_description or self.series_instance_uid
        return f"{self.modality}: {label}"


class ImagingInstance(models.Model):
    """Represent one DICOM instance tracked by metadata and provenance."""

    series = models.ForeignKey(
        ImagingSeries,
        related_name="instances",
        on_delete=models.CASCADE,
    )
    sop_instance_uid = models.CharField(max_length=64, unique=True)
    sop_class_uid = models.CharField(max_length=64, blank=True)
    instance_number = models.IntegerField(blank=True, null=True)
    rows = models.PositiveIntegerField(blank=True, null=True)
    columns = models.PositiveIntegerField(blank=True, null=True)
    file_sha256 = models.CharField(max_length=64, blank=True)
    orthanc_instance_id = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("series_id", "instance_number", "sop_instance_uid")
        indexes = (
            models.Index(fields=["series", "instance_number"], name="img_instance_series_num_idx"),
            models.Index(fields=["file_sha256"], name="imaging_instance_sha_idx"),
            models.Index(fields=["orthanc_instance_id"], name="imaging_instance_orthanc_idx"),
        )

    def __str__(self) -> str:
        if self.instance_number is None:
            return self.sop_instance_uid
        return f"Instance {self.instance_number}: {self.sop_instance_uid}"
