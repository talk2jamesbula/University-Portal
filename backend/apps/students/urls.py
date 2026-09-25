from rest_framework.routers import DefaultRouter

from .views import DocumentFileViewSet, StudentViewSet

router = DefaultRouter()
router.register("documents", DocumentFileViewSet, basename="student-document")
router.register("", StudentViewSet, basename="student")

urlpatterns = router.urls
