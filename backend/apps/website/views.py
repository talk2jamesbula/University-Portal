"""Read-only data for the public website, plus the contact form. No sign-in required."""

from collections import defaultdict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.academics.models import Course, Department, Faculty, Programme, ProgrammeCourse, Semester
from apps.accounts.models import RoleAssignment
from apps.campus.models import Announcement, Event
from apps.core.services import client_ip

from . import chatbot
from .serializers import (
    ChatSerializer,
    ContactMessageSerializer,
    CurriculumCourseSerializer,
    PublicEventSerializer,
    PublicFacultySerializer,
    PublicNewsSerializer,
    PublicProgrammeSerializer,
)

User = get_user_model()


class PublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


def public_news():
    return Announcement.objects.filter(is_public=True).order_by("-pinned", "-created_at")


def upcoming_events():
    return Event.objects.filter(is_public=True, starts_at__gte=timezone.now()).order_by("starts_at")


class OverviewView(PublicView):
    """Home page: headline numbers, latest news and upcoming events."""

    def get(self, request):
        active_programmes = Programme.objects.filter(is_active=True)
        return Response(
            {
                "name": settings.UNIVERSITY_NAME,
                "stats": {
                    "faculties": Faculty.objects.count(),
                    "departments": Department.objects.count(),
                    "programmes": active_programmes.count(),
                    "courses": Course.objects.filter(is_active=True).count(),
                    "students": User.objects.filter(role=User.Role.STUDENT, is_active=True).count(),
                    "staff": User.objects.filter(role=User.Role.STAFF, is_active=True).count(),
                },
                "current_session": getattr(Semester.objects.filter(is_current=True).first(), "session", None),
                "news": PublicNewsSerializer(public_news()[:4], many=True).data,
                "events": PublicEventSerializer(upcoming_events()[:4], many=True).data,
            }
        )


class FacultiesView(PublicView):
    def get(self, request):
        faculties = Faculty.objects.prefetch_related(
            Prefetch("departments", queryset=Department.objects.order_by("name").prefetch_related("programmes"))
        )
        return Response(PublicFacultySerializer(faculties, many=True).data)


PRINCIPAL_OFFICERS = ["vc", "registrar", "bursar"]


def _person(assignment, title):
    user = assignment.user
    return {
        "name": user.get_full_name(),
        "role": title,
        "designation": getattr(getattr(user, "staff_profile", None), "designation", ""),
        "photo_url": user.avatar_url,
    }


class LeadershipView(PublicView):
    """Principal officers, deans and heads of department, from current role appointments."""

    def get(self, request):
        assignments = RoleAssignment.objects.filter(
            user__is_active=True, role__code__in=[*PRINCIPAL_OFFICERS, "dean", "hod"]
        ).select_related("user__staff_profile", "role", "faculty", "department")
        principal, deans, heads = [], [], []
        for a in assignments:
            if a.role.code in PRINCIPAL_OFFICERS:
                principal.append((PRINCIPAL_OFFICERS.index(a.role.code), _person(a, a.role.name)))
            elif a.role.code == "dean" and a.faculty:
                deans.append((a.faculty.name, _person(a, f"Dean, {a.faculty.name}")))
            elif a.role.code == "hod" and a.department:
                heads.append((a.department.name, _person(a, f"Head, Department of {a.department.name}")))
        return Response(
            {
                "principal_officers": [p for _, p in sorted(principal, key=lambda x: x[0])],
                "deans": [p for _, p in sorted(deans, key=lambda x: x[0])],
                "heads_of_department": [p for _, p in sorted(heads, key=lambda x: x[0])],
            }
        )


class ProgrammesView(PublicView):
    def get(self, request):
        programmes = Programme.objects.filter(is_active=True).select_related("department__faculty")
        faculty = request.query_params.get("faculty")
        if faculty:
            programmes = programmes.filter(department__faculty__code=faculty)
        return Response(PublicProgrammeSerializer(programmes, many=True).data)


class ProgrammeDetailView(PublicView):
    """A programme with its curriculum grouped by level and semester."""

    def get(self, request, code):
        programme = get_object_or_404(
            Programme.objects.select_related("department__faculty"), code__iexact=code, is_active=True
        )
        entries = (
            ProgrammeCourse.objects.filter(programme=programme, course__is_active=True)
            .select_related("course")
            .order_by("course__level", "course__semester_number", "-is_compulsory", "course__code")
        )
        grouped = defaultdict(lambda: defaultdict(list))
        for entry in entries:
            grouped[entry.course.level][entry.course.get_semester_number_display()].append(entry)
        curriculum = [
            {
                "level": level,
                "semesters": [
                    {
                        "name": name,
                        "units": sum(e.course.units for e in rows),
                        "courses": CurriculumCourseSerializer(rows, many=True).data,
                    }
                    for name, rows in semesters.items()
                ],
            }
            for level, semesters in sorted(grouped.items())
        ]
        return Response({**PublicProgrammeSerializer(programme).data, "curriculum": curriculum})


class NewsListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicNewsSerializer

    def get_queryset(self):
        return public_news()


class NewsDetailView(generics.RetrieveAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicNewsSerializer

    def get_queryset(self):
        return public_news()


class EventsView(PublicView):
    """Upcoming events (?past=true for recent past events)."""

    def get(self, request):
        if request.query_params.get("past") == "true":
            events = Event.objects.filter(is_public=True, starts_at__lt=timezone.now()).order_by("-starts_at")[:20]
        else:
            events = upcoming_events()
        return Response(PublicEventSerializer(events, many=True).data)


class ContactView(PublicView):
    """Contact form. Rate-limited per visitor; see REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["contact"]."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact"

    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ip_address=client_ip(request))
        return Response(
            {"detail": "Thank you. Your message has been received and we'll reply by email."},
            status=status.HTTP_201_CREATED,
        )


class ChatView(PublicView):
    """The website chatbot: POST {messages: [{role, content}, ...]}, get {reply, suggestions, source}."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def get(self, request):
        return Response({"suggestions": chatbot.SUGGESTIONS, "ai": bool(settings.ANTHROPIC_API_KEY)})

    def post(self, request):
        serializer = ChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(chatbot.reply(serializer.validated_data["messages"]))
