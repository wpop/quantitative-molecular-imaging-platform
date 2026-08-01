"""Domain models for ingestion workflow tracking."""

from django.db import models


class IngestionJob(models.Model):
    """Track a dataset ingestion workflow without clinical identifiers."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class SourceType(models.TextChoices):
        LOCAL_MANIFEST = "local_manifest", "Local manifest"
        ORTHANC = "orthanc", "Orthanc"
        TCIA_MANIFEST = "tcia_manifest", "TCIA manifest"

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    source_name = models.CharField(max_length=255)
    source_uri = models.CharField(max_length=512, blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "source_name")
        indexes = (
            models.Index(fields=["status"], name="ingestion_job_status_idx"),
            models.Index(fields=["source_type"], name="ingestion_job_source_type_idx"),
            models.Index(fields=["created_at"], name="ingestion_job_created_idx"),
        )

    def __str__(self) -> str:
        return f"{self.source_name} ({self.status})"


class IngestionJobEvent(models.Model):
    """Store structured ingestion log events."""

    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    job = models.ForeignKey(
        IngestionJob,
        related_name="events",
        on_delete=models.CASCADE,
    )
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    message = models.TextField()
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = (
            models.Index(fields=["job", "created_at"], name="ingest_event_job_created_idx"),
            models.Index(fields=["level"], name="ingestion_event_level_idx"),
        )

    def __str__(self) -> str:
        return f"{self.level}: {self.message[:80]}"
