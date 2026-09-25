from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CheckInView,
    CorrectionViewSet,
    MyAttendanceView,
    OfferingStatsView,
    OfferingUploadTemplateView,
    OfferingUploadView,
    RecordCorrectionView,
    ReportExportView,
    ReportView,
    SessionViewSet,
)

router = DefaultRouter()
router.register("sessions", SessionViewSet, basename="attendance-session")
router.register("corrections", CorrectionViewSet, basename="attendance-correction")

urlpatterns = [
    path("check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("me/", MyAttendanceView.as_view(), name="attendance-me"),
    path("offerings/<int:pk>/stats/", OfferingStatsView.as_view(), name="attendance-offering-stats"),
    path("offerings/<int:pk>/upload/", OfferingUploadView.as_view(), name="attendance-offering-upload"),
    path(
        "offerings/<int:pk>/upload-template/", OfferingUploadTemplateView.as_view(), name="attendance-upload-template"
    ),
    path("records/<int:pk>/correction/", RecordCorrectionView.as_view(), name="attendance-record-correction"),
    path("reports/", ReportView.as_view(), name="attendance-report"),
    path("reports/export/", ReportExportView.as_view(), name="attendance-report-export"),
    *router.urls,
]
