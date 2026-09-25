from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet, EventViewSet

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("events", EventViewSet, basename="event")

urlpatterns = router.urls
