from django.contrib.auth import get_user_model
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import StudentProfile
from apps.accounts.permissions import IsStudent, ReadOnlyOrRequires, Requires
from apps.core.models import Notification
from apps.core.services import audit, notify

from .models import Course, CourseOffering, Department, Enrollment, Faculty, Programme, ProgrammeCourse, Semester
from .serializers import (
    CourseCreateSerializer,
    CourseSerializer,
    DepartmentSerializer,
    FacultySerializer,
    OfferingSerializer,
    ProgrammeCourseSerializer,
    ProgrammeSerializer,
    RegistrationSerializer,
    RosterEntrySerializer,
    SemesterSerializer,
)
from .services import (
    available_offerings,
    current_semester,
    drop_course,
    register_course,
    registration_summary,
    student_results,
)

User = get_user_model()
REGISTERED = Enrollment.Status.REGISTERED
MANAGE = ReadOnlyOrRequires("academics.manage")


def with_registered_count(queryset):
    return queryset.annotate(
        registered_count=Count("enrollments", filter=Q(enrollments__status=REGISTERED), distinct=True)
    )


# --- Academic structure (read: everyone signed in; write: academics.manage) ---------------------


class ManagedViewSet(viewsets.ModelViewSet):
    """Structure records: changes are audited, and records still in use can't be deleted."""

    permission_classes = [MANAGE]
    audit_name = "record"

    def perform_create(self, serializer):
        obj = serializer.save()
        audit(self.request, f"{self.audit_name}.create", obj, f"Created {self.audit_name} {obj}")

    def perform_update(self, serializer):
        obj = serializer.save()
        audit(self.request, f"{self.audit_name}.update", obj, f"Updated {self.audit_name} {obj}")

    def perform_destroy(self, instance):
        label = str(instance)
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(f"{label} is still in use and can't be deleted. Mark it inactive instead.") from None
        audit(self.request, f"{self.audit_name}.delete", None, f"Deleted {self.audit_name} {label}")


class FacultyViewSet(ManagedViewSet):
    audit_name = "faculty"
    queryset = Faculty.objects.annotate(department_count=Count("departments")).order_by("name")
    serializer_class = FacultySerializer
    search_fields = ["code", "name"]
    pagination_class = None


class DepartmentViewSet(ManagedViewSet):
    audit_name = "department"
    queryset = (
        Department.objects.select_related("faculty").annotate(programme_count=Count("programmes")).order_by("name")
    )
    serializer_class = DepartmentSerializer
    filterset_fields = ["faculty"]
    search_fields = ["code", "name"]
    pagination_class = None


class ProgrammeViewSet(ManagedViewSet):
    audit_name = "programme"
    queryset = Programme.objects.select_related("department__faculty")
    serializer_class = ProgrammeSerializer
    filterset_fields = ["department", "department__faculty", "degree", "is_active"]
    search_fields = ["code", "name"]
    pagination_class = None


class SemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    permission_classes = [MANAGE]
    filterset_fields = ["is_current", "registration_open", "session"]
    pagination_class = None

    def perform_update(self, serializer):
        was_open = serializer.instance.registration_open
        semester = serializer.save()
        if semester.registration_open and not was_open:
            can_register = [StudentProfile.Status.ACTIVE, StudentProfile.Status.PROBATION]
            students = User.objects.filter(role=User.Role.STUDENT, student_profile__status__in=can_register)
            notify(
                students,
                f"Course registration for {semester} is now open",
                "Register your courses and print your course form before the deadline.",
                link="/portal/registration",
                category=Notification.Category.REGISTRATION,
                email=True,
                sms=True,
            )
        audit(self.request, "semester.update", semester, f"Updated {semester}")


class CourseViewSet(ManagedViewSet):
    """The course catalogue. Creating a course can also add it to curricula and offer it."""

    audit_name = "course"
    serializer_class = CourseSerializer
    filterset_fields = ["department", "department__faculty", "level", "semester_number", "is_active"]
    search_fields = ["code", "title"]
    ordering_fields = ["code", "level", "title"]

    def get_queryset(self):
        return (
            Course.objects.select_related("department")
            .annotate(
                programme_count=Count("programmes", distinct=True),
                offering_count=Count("offerings", distinct=True),
            )
            .order_by("code")
        )

    def get_serializer_class(self):
        return CourseCreateSerializer if self.action == "create" else CourseSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        course = self.get_queryset().get(pk=serializer.instance.pk)
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class ProgrammeCourseViewSet(ManagedViewSet):
    """Programme curricula: which courses each programme takes, compulsory or elective."""

    audit_name = "curriculum"

    queryset = ProgrammeCourse.objects.select_related("course__department", "programme__department")
    serializer_class = ProgrammeCourseSerializer
    filterset_fields = ["programme", "course", "course__level", "course__semester_number", "is_compulsory"]
    pagination_class = None


class OfferingViewSet(ManagedViewSet):
    """Courses offered in a semester. ?mine=true gives a lecturer's courses or a student's registrations."""

    audit_name = "offering"

    serializer_class = OfferingSerializer
    filterset_fields = ["semester", "course", "course__department", "course__level", "lecturer"]
    search_fields = ["course__code", "course__title", "lecturer__last_name"]
    ordering_fields = ["course__code", "course__level"]

    def get_queryset(self):
        qs = with_registered_count(
            CourseOffering.objects.select_related("course__department", "semester", "lecturer")
        ).order_by("course__code")
        if self.request.query_params.get("mine") == "true":
            user = self.request.user
            if user.is_student:
                qs = qs.filter(enrollments__student=user, enrollments__status=REGISTERED)
            else:
                qs = qs.filter(lecturer=user)
        return qs

    def get_permissions(self):
        if self.action == "roster":
            return [IsAuthenticated()]  # lecturer / officer check happens on the object
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def roster(self, request, pk=None):
        offering = self.get_object()
        user = request.user
        if offering.lecturer_id != user.id and not user.has_permission(
            "results.approve_department",
            "results.approve_faculty",
            "results.publish",
            "attendance.view",
        ):
            raise PermissionDenied("Only the course lecturer and result officers can view the class list.")
        enrollments = (
            offering.enrollments.filter(status=REGISTERED)
            .select_related("student__student_profile")
            .order_by("student__university_id")
        )
        return Response(RosterEntrySerializer(enrollments, many=True).data)


# --- Students: registration and results ---------------------------------------------------------


def _semester_from(request):
    semester_id = request.query_params.get("semester") or request.data.get("semester")
    semester = get_object_or_404(Semester, pk=semester_id) if semester_id else current_semester()
    if semester is None:
        raise ValidationError("There is no current semester.")
    return semester


class RegistrationView(APIView):
    """GET: the student's registration for a semester plus the courses they may add.
    POST {"offering": id, "action": "add" | "drop"}: register or drop a course."""

    permission_classes = [IsStudent]

    def get(self, request):
        semester = _semester_from(request)
        summary = registration_summary(request.user, semester)
        registered_ids = {e.offering_id for e in summary["registered"]}
        available = [
            {
                **OfferingSerializer(offering).data,
                "is_compulsory": compulsory,
                "is_carryover": carryover,
                "is_registered": offering.pk in registered_ids,
            }
            for offering, compulsory, carryover in available_offerings(request.user, semester)
        ]
        return Response(
            {
                "semester": SemesterSerializer(semester).data,
                "state": summary["state"],
                "units": summary["units"],
                "min_units": summary["min_units"],
                "max_units": summary["max_units"],
                "registered": RegistrationSerializer(summary["registered"], many=True).data,
                "available": available,
            }
        )

    def post(self, request):
        offering = get_object_or_404(CourseOffering, pk=request.data.get("offering"))
        if request.data.get("action") == "drop":
            enrollment = drop_course(request.user, offering)
            return Response(RegistrationSerializer(enrollment).data)
        enrollment = register_course(request.user, offering)
        return Response(RegistrationSerializer(enrollment).data, status=status.HTTP_201_CREATED)


class RegistrationHistoryView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        semesters = Semester.objects.filter(
            offerings__enrollments__student=request.user, offerings__enrollments__status=REGISTERED
        ).distinct()
        history = []
        for semester in semesters:
            summary = registration_summary(request.user, semester)
            history.append(
                {
                    "semester": SemesterSerializer(semester).data,
                    "units": summary["units"],
                    "courses": RegistrationSerializer(summary["registered"], many=True).data,
                }
            )
        return Response(history)


def serialize_results(results):
    return {
        "cgpa": results["cgpa"],
        "units_taken": results["units_taken"],
        "units_passed": results["units_passed"],
        "standing": results["standing"],
        "degree_class": results["degree_class"],
        "semesters": [
            {
                "semester": SemesterSerializer(row["semester"]).data,
                "gpa": row["gpa"],
                "units_taken": row["units_taken"],
                "units_passed": row["units_passed"],
                "courses": [
                    {
                        "code": e.offering.course.code,
                        "title": e.offering.course.title,
                        "units": e.offering.course.units,
                        "ca_score": e.ca_score,
                        "exam_score": e.exam_score,
                        "total_score": e.total_score,
                        "grade": e.grade,
                        "grade_points": e.grade_points,
                        "is_carryover": e.is_carryover,
                    }
                    for e in row["enrollments"]
                ],
            }
            for row in results["semesters"]
        ],
    }


class ResultsView(APIView):
    """A student's published results, GPA per semester, CGPA and academic standing."""

    permission_classes = [IsStudent]

    def get(self, request):
        return Response(serialize_results(student_results(request.user)))


class LecturersView(APIView):
    """Staff who can be assigned to teach courses (for offering forms)."""

    permission_classes = [Requires("academics.manage")]

    def get(self, request):
        staff = (
            User.objects.filter(role=User.Role.STAFF, is_active=True)
            .select_related("department")
            .prefetch_related("assignments__role")
            .order_by("last_name", "first_name")
        )
        return Response(
            [
                {"id": u.id, "name": u.get_full_name(), "department": u.department.name if u.department else None}
                for u in staff
                if u.has_permission("courses.teach")
            ]
        )
