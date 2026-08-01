"""Read-only viewsets for imaging metadata APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.imaging.api.serializers import (
    ImagingInstanceSerializer,
    ImagingSeriesSerializer,
    ImagingStudySerializer,
)
from apps.imaging.models import ImagingInstance, ImagingSeries, ImagingStudy

if TYPE_CHECKING:
    from rest_framework.request import Request


class ImagingStudyViewSet(ReadOnlyModelViewSet[ImagingStudy]):
    """List and retrieve study metadata."""

    serializer_class = ImagingStudySerializer
    queryset = ImagingStudy.objects.annotate(series_count=Count("series")).order_by(
        "study_instance_uid",
    )

    def get_queryset(self) -> QuerySet[ImagingStudy]:
        queryset = super().get_queryset()
        request: Request = self.request
        study_instance_uid = request.query_params.get("study_instance_uid")
        source_dataset = request.query_params.get("source_dataset")
        source_subject_id = request.query_params.get("source_subject_id")
        if study_instance_uid:
            queryset = queryset.filter(study_instance_uid=study_instance_uid)
        if source_dataset:
            queryset = queryset.filter(source_dataset=source_dataset)
        if source_subject_id:
            queryset = queryset.filter(source_subject_id=source_subject_id)
        return queryset


class ImagingSeriesViewSet(ReadOnlyModelViewSet[ImagingSeries]):
    """List and retrieve series metadata."""

    serializer_class = ImagingSeriesSerializer
    queryset = ImagingSeries.objects.select_related("study").order_by(
        "study__study_instance_uid",
        "modality",
        "series_instance_uid",
    )

    def get_queryset(self) -> QuerySet[ImagingSeries]:
        queryset = super().get_queryset()
        request: Request = self.request
        study_instance_uid = request.query_params.get("study_instance_uid")
        series_instance_uid = request.query_params.get("series_instance_uid")
        modality = request.query_params.get("modality")
        source_dataset = request.query_params.get("source_dataset")
        source_subject_id = request.query_params.get("source_subject_id")
        if study_instance_uid:
            queryset = queryset.filter(study__study_instance_uid=study_instance_uid)
        if series_instance_uid:
            queryset = queryset.filter(series_instance_uid=series_instance_uid)
        if modality:
            queryset = queryset.filter(modality=modality)
        if source_dataset:
            queryset = queryset.filter(study__source_dataset=source_dataset)
        if source_subject_id:
            queryset = queryset.filter(study__source_subject_id=source_subject_id)
        return queryset


class ImagingInstanceViewSet(ReadOnlyModelViewSet[ImagingInstance]):
    """List and retrieve DICOM instance metadata."""

    serializer_class = ImagingInstanceSerializer
    queryset = ImagingInstance.objects.select_related("series", "series__study").order_by(
        "series__study__study_instance_uid",
        "series__series_instance_uid",
        "instance_number",
        "sop_instance_uid",
    )

    def get_queryset(self) -> QuerySet[ImagingInstance]:
        queryset = super().get_queryset()
        request: Request = self.request
        study_instance_uid = request.query_params.get("study_instance_uid")
        series_instance_uid = request.query_params.get("series_instance_uid")
        modality = request.query_params.get("modality")
        source_dataset = request.query_params.get("source_dataset")
        source_subject_id = request.query_params.get("source_subject_id")
        if study_instance_uid:
            queryset = queryset.filter(series__study__study_instance_uid=study_instance_uid)
        if series_instance_uid:
            queryset = queryset.filter(series__series_instance_uid=series_instance_uid)
        if modality:
            queryset = queryset.filter(series__modality=modality)
        if source_dataset:
            queryset = queryset.filter(series__study__source_dataset=source_dataset)
        if source_subject_id:
            queryset = queryset.filter(series__study__source_subject_id=source_subject_id)
        return queryset
