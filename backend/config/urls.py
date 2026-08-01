"""Root URL configuration for the backend project."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.imaging.api.overview import MetadataOverviewView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/overview/", MetadataOverviewView.as_view(), name="metadata-overview"),
    path("api/v1/imaging/", include("apps.imaging.api.urls")),
    path("api/v1/ingestion/", include("apps.ingestion.api.urls")),
]
