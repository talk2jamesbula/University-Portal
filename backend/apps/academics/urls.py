from django.urls import path
from rest_framework.routers import DefaultRouter

from .dashboard import DashboardView
from .views import (
    CourseViewSet,
    DepartmentViewSet,
    FacultyViewSet,
    LecturersView,
    OfferingViewSet,
    ProgrammeCourseViewSet,
    ProgrammeViewSet,
    RegistrationHistoryView,
    RegistrationView,
    ResultsView,
    SemesterViewSet,
)

router = DefaultRouter()
router.register("faculties", FacultyViewSet)
router.register("departments", DepartmentViewSet)
router.register("programmes", ProgrammeViewSet)
router.register("semesters", SemesterViewSet)
router.register("courses", CourseViewSet, basename="course")
router.register("curriculum", ProgrammeCourseViewSet)
router.register("offerings", OfferingViewSet, basename="offering")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("lecturers/", LecturersView.as_view(), name="lecturers"),
    path("registration/", RegistrationView.as_view(), name="registration"),
    path("registration/history/", RegistrationHistoryView.as_view(), name="registration-history"),
    path("results/", ResultsView.as_view(), name="results"),
    *router.urls,
]
