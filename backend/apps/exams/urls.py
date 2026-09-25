from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AnswerView,
    AttemptEventView,
    AttemptView,
    ExamViewSet,
    MyExamCardView,
    MyExamsView,
    QuestionView,
    StartAttemptView,
    StudentExamCardView,
    SubmitAttemptView,
    VenueViewSet,
    VerifyCheckInView,
    VerifyView,
)

router = DefaultRouter()
router.register("venues", VenueViewSet, basename="exam-venue")
router.register("timetable", ExamViewSet, basename="exam")

urlpatterns = [
    path("me/", MyExamsView.as_view(), name="exams-me"),
    path("me/card/", MyExamCardView.as_view(), name="exams-my-card"),
    path("cards/<int:pk>/", StudentExamCardView.as_view(), name="exams-student-card"),
    path("questions/<int:pk>/", QuestionView.as_view(), name="exams-question"),
    path("timetable/<int:pk>/start/", StartAttemptView.as_view(), name="exams-start"),
    path("attempts/<int:pk>/", AttemptView.as_view(), name="exams-attempt"),
    path("attempts/<int:pk>/answer/", AnswerView.as_view(), name="exams-answer"),
    path("attempts/<int:pk>/event/", AttemptEventView.as_view(), name="exams-event"),
    path("attempts/<int:pk>/submit/", SubmitAttemptView.as_view(), name="exams-submit"),
    path("verify/", VerifyView.as_view(), name="exams-verify"),
    path("verify/check-in/", VerifyCheckInView.as_view(), name="exams-check-in"),
    *router.urls,
]
