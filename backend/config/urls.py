"""Root URL configuration for the backend project."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/imaging/", include("apps.imaging.api.urls")),
    path("api/v1/ingestion/", include("apps.ingestion.api.urls")),
]
