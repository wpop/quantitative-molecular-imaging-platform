"""URL routes for read-only imaging metadata APIs."""

from rest_framework.routers import DefaultRouter

from apps.imaging.api.views import (
    ImagingInstanceViewSet,
    ImagingSeriesViewSet,
    ImagingStudyViewSet,
)

app_name = "imaging-api"

router = DefaultRouter()
router.register("studies", ImagingStudyViewSet, basename="imaging-study")
router.register("series", ImagingSeriesViewSet, basename="imaging-series")
router.register("instances", ImagingInstanceViewSet, basename="imaging-instance")

urlpatterns = router.urls
