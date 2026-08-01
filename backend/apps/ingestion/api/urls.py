"""URL routes for read-only ingestion metadata APIs."""

from rest_framework.routers import DefaultRouter

from apps.ingestion.api.views import IngestionJobEventViewSet, IngestionJobViewSet

app_name = "ingestion-api"

router = DefaultRouter()
router.register("jobs", IngestionJobViewSet, basename="ingestion-job")
router.register("events", IngestionJobEventViewSet, basename="ingestion-event")

urlpatterns = router.urls
