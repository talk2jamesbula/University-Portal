"""The home screen: one request that returns everything the signed-in user's dashboard shows."""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember
from apps.campus.models import Event
from apps.campus.selectors import visible_announcements
from apps.core.models import Notification
from apps.finance.models import PaymentProof
from apps.finance.services import account_summary

from .models import CourseOffering, Enrollment
from .serializers import OfferingSerializer, SemesterSerializer
from .services import current_semester, registration_summary, student_results

User = get_user_model()
REGISTERED = Enrollment.Status.REGISTERED
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _student(user, semester):
    profile = getattr(user, "student_profile", None)
    results = student_results(user)
    account = account_summary(user)
    data = {
        "profile": {
            "matric_number": user.university_id,
            "programme": profile.programme.title if profile else None,
            "department": profile.programme.department.name if profile else None,
            "level": profile.level if profile else None,
            "status": profile.get_status_display() if profile else None,
        },
        "stats": {
            "cgpa": results["cgpa"],
            "standing": results["standing"],
            "units_passed": results["units_passed"],
            "balance": account["balance"],
            "overdue": account["overdue"],
            "next_due_date": account["next_due_date"],
        },
        "registration": None,
        "schedule": [],
    }
    if semester:
        summary = registration_summary(user, semester)
        data["registration"] = {
            "state": summary["state"],
            "units": summary["units"],
            "min_units": summary["min_units"],
            "max_units": summary["max_units"],
            "is_open": semester.registration_open,
        }
        data["schedule"] = OfferingSerializer([e.offering for e in summary["registered"]], many=True).data
    return data


def _staff(user, semester):
    offerings = CourseOffering.objects.filter(lecturer=user).select_related("course", "semester")
    if semester:
        offerings = offerings.filter(semester=semester)
    offerings = list(
        offerings.annotate(
            registered_count=Count("enrollments", filter=Q(enrollments__status=REGISTERED), distinct=True)
        )
    )
    today = WEEKDAYS[timezone.localdate().weekday()]
    pending = Enrollment.objects.filter(
        offering__in=offerings,
        status=REGISTERED,
        result_status__in=[Enrollment.ResultStatus.PENDING, Enrollment.ResultStatus.DRAFT],
    ).count()
    return {
        "stats": {
            "courses_teaching": len(offerings),
            "total_students": sum(o.registered_count for o in offerings),
            "classes_today": sum(1 for o in offerings if today in o.day_list),
            "pending_results": pending,
        },
        "schedule": OfferingSerializer(offerings, many=True).data,
        "classes_today": OfferingSerializer(
            sorted((o for o in offerings if today in o.day_list), key=lambda o: o.start_time or timezone.now().time()),
            many=True,
        ).data,
    }


def _admin(user, semester):
    active = User.objects.filter(is_active=True)
    return {
        "stats": {
            "students": active.filter(role=User.Role.STUDENT).count(),
            "staff": active.filter(role=User.Role.STAFF).count(),
            "offerings": CourseOffering.objects.filter(semester=semester).count() if semester else 0,
            "registrations": Enrollment.objects.filter(offering__semester=semester, status=REGISTERED).count()
            if semester
            else 0,
            "pending_proofs": PaymentProof.objects.filter(status=PaymentProof.Status.PENDING).count(),
        },
        "schedule": [],
    }


class DashboardView(APIView):
    permission_classes = [IsMember]  # applicants have their own home page

    def get(self, request):
        user = request.user
        semester = current_semester()
        if user.is_student:
            data = _student(user, semester)
        elif user.is_staff_member and not user.has_permission("reports.view"):
            data = _staff(user, semester)
        else:
            data = {**_admin(user, semester), **({"teaching": _staff(user, semester)} if user.is_staff_member else {})}

        now = timezone.now()
        data.update(
            {
                "semester": SemesterSerializer(semester).data if semester else None,
                "announcements": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "priority": a.priority,
                        "created_at": a.created_at,
                        "course_code": a.offering.course.code if a.offering else None,
                        "department_name": a.department.name if a.department else None,
                    }
                    for a in visible_announcements(user)[:5]
                ],
                "notifications": [
                    {"id": n.id, "title": n.title, "link": n.link, "created_at": n.created_at, "read": bool(n.read_at)}
                    for n in Notification.objects.filter(user=user)[:5]
                ],
                "unread_notifications": Notification.objects.filter(user=user, read_at__isnull=True).count(),
                "upcoming_events": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "starts_at": e.starts_at,
                        "category": e.category,
                        "location": e.location,
                    }
                    for e in Event.objects.filter(starts_at__gte=now)[:4]
                ],
                "academic_calendar": [
                    {"id": e.id, "title": e.title, "starts_at": e.starts_at, "category": e.category}
                    for e in Event.objects.filter(
                        starts_at__gte=now, category__in=[Event.Category.ACADEMIC, Event.Category.DEADLINE]
                    )[:6]
                ],
            }
        )
        return Response(data)
