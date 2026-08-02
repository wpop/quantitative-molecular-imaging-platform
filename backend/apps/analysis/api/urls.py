"""URL routes for read-only analysis metadata APIs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.analysis.api.views import (
    AnalysisRunViewSet,
    MeasurementResultViewSet,
    VisualizationArtifactViewSet,
)

router = DefaultRouter()
router.register("artifacts", VisualizationArtifactViewSet, basename="visualization-artifact")
router.register("runs", AnalysisRunViewSet, basename="analysis-run")
router.register("results", MeasurementResultViewSet, basename="measurement-result")

app_name = "analysis-api"

urlpatterns = [
    path("", include(router.urls)),
]
