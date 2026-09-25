from django.urls import path

from .views import (
    ChatView,
    ContactView,
    EventsView,
    FacultiesView,
    LeadershipView,
    NewsDetailView,
    NewsListView,
    OverviewView,
    ProgrammeDetailView,
    ProgrammesView,
)

urlpatterns = [
    path("overview/", OverviewView.as_view(), name="public-overview"),
    path("faculties/", FacultiesView.as_view(), name="public-faculties"),
    path("leadership/", LeadershipView.as_view(), name="public-leadership"),
    path("programmes/", ProgrammesView.as_view(), name="public-programmes"),
    path("programmes/<str:code>/", ProgrammeDetailView.as_view(), name="public-programme"),
    path("news/", NewsListView.as_view(), name="public-news"),
    path("news/<int:pk>/", NewsDetailView.as_view(), name="public-news-detail"),
    path("events/", EventsView.as_view(), name="public-events"),
    path("contact/", ContactView.as_view(), name="public-contact"),
    path("chat/", ChatView.as_view(), name="public-chat"),
]
