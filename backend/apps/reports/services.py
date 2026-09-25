"""Analytics for the management dashboard.

Every figure is computed in the database from live records, and limited to what the viewer may see:
the whole University for the VC, Registrar and Bursar; their own faculty for a Dean (scoped `reports.view`).
Fee figures need `finance.view`.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from apps.academics.grading import GRADE_SCALE, PASS_MARK
from apps.academics.models import Enrollment, Faculty, Semester
from apps.academics.services import current_semester
from apps.accounts.models import StudentProfile
from apps.admissions.models import AdmissionCycle, Application
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.finance.models import Charge, Payment

User = get_user_model()
Status = StudentProfile.Status
IN_SCHOOL = (Status.ACTIVE, Status.PROBATION)

TOTAL = ExpressionWrapper(F("ca_score") + F("exam_score"), output_field=DecimalField(max_digits=6, decimal_places=2))


def _series(rows, label="label", value="value"):
    return [{"label": r[label] or "Unknown", "value": r[value] or 0} for r in rows]


def _money(value):
    return float(value or Decimal("0"))


class Analytics:
    def __init__(self, user):
        self.user = user
        self.scope = user.permission_scope("reports.view")

    def q(self, department_path):
        """Limit a queryset to the viewer's faculty or department (nothing for university-wide viewers)."""
        return self.user.scope_filter("reports.view", department_path)

    def scope_label(self):
        if self.scope is None:
            return "Whole university"
        departments, faculties = self.scope
        names = list(Faculty.objects.filter(pk__in=faculties).values_list("name", flat=True))
        return ", ".join(names) or f"{len(departments)} department(s)"

    # --- Students ---------------------------------------------------------------------------------

    def students(self):
        profiles = StudentProfile.objects.filter(self.q("programme__department"), user__is_active=True)
        by_faculty = (
            profiles.filter(status__in=IN_SCHOOL)
            .values(label=F("programme__department__faculty__name"))
            .annotate(value=Count("id"))
            .order_by("-value")
        )
        by_level = profiles.filter(status__in=IN_SCHOOL).values("level").annotate(value=Count("id")).order_by("level")
        by_status = dict(profiles.values_list("status").annotate(n=Count("id")))
        by_gender = dict(profiles.filter(status__in=IN_SCHOOL).values_list("gender").annotate(n=Count("id")))
        return {
            "total": profiles.filter(status__in=IN_SCHOOL).count(),
            "by_faculty": _series(by_faculty),
            "by_level": [{"label": f"{r['level']} L", "value": r["value"]} for r in by_level],
            "by_status": [
                {"key": s, "label": Status(s).label.split(" (")[0], "value": by_status[s]}
                for s in Status.values
                if by_status.get(s)
            ],
            "by_gender": [
                {"key": g, "label": StudentProfile.Gender(g).label, "value": by_gender.get(g, 0)}
                for g in StudentProfile.Gender.values
            ],
        }

    def registration(self, semester):
        if not semester:
            return None
        in_school = User.objects.filter(
            self.q("student_profile__programme__department"),
            role=User.Role.STUDENT,
            is_active=True,
            student_profile__status__in=IN_SCHOOL,
        )
        registered = in_school.filter(
            enrollments__offering__semester=semester, enrollments__status=Enrollment.Status.REGISTERED
        ).distinct()
        by_level = []
        for level in sorted(set(in_school.values_list("student_profile__level", flat=True))):
            total = in_school.filter(student_profile__level=level).count()
            done = registered.filter(student_profile__level=level).count()
            by_level.append({"label": f"{level} L", "value": round(done * 100 / total, 1) if total else 0})
        total, done = in_school.count(), registered.count()
        return {
            "registered": done,
            "not_registered": total - done,
            "rate": round(done * 100 / total, 1) if total else None,
            "by_level": by_level,
        }

    # --- Money ------------------------------------------------------------------------------------

    def finance(self):
        if not self.user.has_permission("finance.view"):
            return None
        payments = Payment.objects.filter(
            self.q("student__student_profile__programme__department"), status=Payment.Status.COMPLETED
        )
        now = timezone.localtime()
        start = (now.replace(day=1) - timedelta(days=335)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly = {
            timezone.localtime(r["month"]).strftime("%Y-%m"): r["total"]
            for r in payments.filter(paid_at__gte=start)
            .annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Sum("amount"))
        }
        months, cursor = [], start
        for _ in range(12):
            key = cursor.strftime("%Y-%m")
            months.append({"label": cursor.strftime("%b %y"), "value": _money(monthly.get(key))})
            cursor = (cursor + timedelta(days=32)).replace(day=1)
        charges = Charge.objects.filter(self.q("student__student_profile__programme__department"))
        charged, paid = (
            _money(charges.aggregate(t=Sum("amount"))["t"]),
            _money(payments.aggregate(t=Sum("amount"))["t"]),
        )
        by_method = payments.values("method").annotate(total=Sum("amount")).order_by("-total")
        faculty = "student__student_profile__programme__department__faculty__name"
        charged_by = dict(charges.values_list(faculty).annotate(t=Sum("amount")))
        paid_by = dict(payments.values_list(faculty).annotate(t=Sum("amount")))
        outstanding = [
            {"label": name or "Unknown", "value": max(_money(total) - _money(paid_by.get(name)), 0)}
            for name, total in charged_by.items()
        ]
        return {
            "monthly": months,
            "charged": charged,
            "paid": paid,
            "outstanding": max(charged - paid, 0),
            "collection_rate": round(paid * 100 / charged, 1) if charged else None,
            "by_method": [
                {"key": r["method"], "label": Payment.Method(r["method"]).label, "value": _money(r["total"])}
                for r in by_method
            ],
            "outstanding_by_faculty": sorted(outstanding, key=lambda r: -r["value"]),
        }

    # --- Admissions -------------------------------------------------------------------------------

    def admissions(self):
        cycle = AdmissionCycle.current()
        if not cycle:
            return None
        applications = Application.objects.filter(cycle=cycle)
        if self.scope is not None:
            applications = applications.filter(self.q("programme__department"))
        counts = dict(applications.values_list("status").annotate(n=Count("id")))
        S = Application.Status
        reached = {  # how many got at least this far
            "Started": sum(counts.values()),
            "Submitted": sum(counts.get(s, 0) for s in S.values if s != S.DRAFT),
            "Screened": sum(counts.get(s, 0) for s in (S.SCREENING, S.APPROVED, S.WAITLISTED, S.ADMITTED, S.ACCEPTED))
            + applications.filter(status=S.REJECTED, screening_score__isnull=False).count(),
            "Offered": sum(counts.get(s, 0) for s in (S.APPROVED, S.ADMITTED, S.ACCEPTED)),
            "Accepted": counts.get(S.ACCEPTED, 0),
        }
        weeks = (
            applications.filter(submitted_at__isnull=False)
            .annotate(week=TruncWeek("submitted_at"))
            .values("week")
            .annotate(value=Count("id"))
            .order_by("week")
        )
        by_programme = (
            applications.exclude(status=S.DRAFT)
            .values(label=F("programme__name"))
            .annotate(value=Count("id"))
            .order_by("-value")[:6]
        )
        return {
            "session": cycle.session,
            "funnel": [{"label": k, "value": v} for k, v in reached.items()],
            "weekly": [{"label": f"{timezone.localtime(r['week']):%d %b}", "value": r["value"]} for r in weeks][-12:],
            "by_programme": _series(by_programme),
            "by_status": [{"key": s, "label": S(s).label, "value": counts[s]} for s in S.values if counts.get(s)],
        }

    # --- Results ----------------------------------------------------------------------------------

    def academics(self):
        published = Enrollment.objects.filter(
            self.q("offering__course__department"),
            result_status=Enrollment.ResultStatus.PUBLISHED,
            ca_score__isnull=False,
            exam_score__isnull=False,
        )
        semester = (
            Semester.objects.filter(offerings__enrollments__in=published).distinct().order_by("-start_date").first()
        )
        if not semester:
            return None
        rows = published.filter(offering__semester=semester).annotate(total=TOTAL)
        grade = Case(
            *[When(total__gte=minimum, then=Value(letter)) for minimum, letter, _ in GRADE_SCALE], default=Value("F")
        )
        points = Case(
            *[When(total__gte=minimum, then=Value(p)) for minimum, _, p in GRADE_SCALE],
            default=Value(0),
            output_field=IntegerField(),
        )
        distribution = dict(rows.annotate(g=grade).values_list("g").annotate(n=Count("id")))
        by_department = (
            rows.annotate(weighted=points * F("offering__course__units"))
            .values(label=F("offering__course__department__name"))
            .annotate(points=Sum("weighted"), units=Sum("offering__course__units"))
            .order_by("label")
        )
        total = sum(distribution.values())
        passed = rows.filter(total__gte=PASS_MARK).count()
        return {
            "semester": semester.name,
            "grade_distribution": [{"label": g, "value": distribution.get(g, 0)} for _, g, _ in GRADE_SCALE],
            "gpa_by_department": [
                {"label": r["label"], "value": round(r["points"] / r["units"], 2) if r["units"] else 0}
                for r in by_department
            ],
            "pass_rate": round(passed * 100 / total, 1) if total else None,
            "results": total,
        }

    # --- Attendance -------------------------------------------------------------------------------

    def attendance(self, semester):
        if not semester:
            return None
        records = AttendanceRecord.objects.filter(
            self.q("session__offering__course__department"),
            session__offering__semester=semester,
            session__status=AttendanceSession.Status.CLOSED,
        )
        attended = Q(status__in=AttendanceRecord.ATTENDED)
        by_faculty = (
            records.values(label=F("session__offering__course__department__faculty__name"))
            .annotate(total=Count("id"), present=Count("id", filter=attended))
            .order_by("label")
        )
        weekly = (
            records.annotate(week=TruncWeek("session__date"))
            .values("week")
            .annotate(total=Count("id"), present=Count("id", filter=attended))
            .order_by("week")
        )
        totals = records.aggregate(total=Count("id"), present=Count("id", filter=attended))
        return {
            "overall": round(totals["present"] * 100 / totals["total"], 1) if totals["total"] else None,
            "by_faculty": [
                {"label": r["label"], "value": round(r["present"] * 100 / r["total"], 1)}
                for r in by_faculty
                if r["total"]
            ],
            "weekly": [
                {"label": f"{r['week']:%d %b}", "value": round(r["present"] * 100 / r["total"], 1)}
                for r in weekly
                if r["total"]
            ],
        }

    def build(self):
        semester = current_semester()
        return {
            "scope": self.scope_label(),
            "semester": semester.name if semester else None,
            "generated_at": timezone.now(),
            "students": self.students(),
            "registration": self.registration(semester),
            "finance": self.finance(),
            "admissions": self.admissions(),
            "academics": self.academics(),
            "attendance": self.attendance(semester),
        }
