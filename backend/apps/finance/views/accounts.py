from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Semester
from apps.accounts.permissions import Requires, StudentOrRequires

from ..documents import invoice_number, invoice_pdf
from ..models import Charge, Payment, PaymentProof
from ..serializers import ChargeSerializer, PaymentSerializer, StudentBalanceSerializer
from ..services import account_summary
from .common import User, pdf_response, resolve_student

MONEY = DecimalField(max_digits=12, decimal_places=2)
ZERO = Decimal("0")


def with_balances(queryset):
    """Annotate users with total_charged, total_paid and balance (charged - paid)."""
    charged = Charge.objects.filter(student=OuterRef("pk")).values("student").annotate(t=Sum("amount")).values("t")
    paid = (
        Payment.objects.filter(student=OuterRef("pk"), status=Payment.Status.COMPLETED)
        .values("student")
        .annotate(t=Sum("amount"))
        .values("t")
    )
    zero = Value(ZERO, output_field=MONEY)
    return queryset.annotate(
        total_charged=Coalesce(Subquery(charged, output_field=MONEY), zero),
        total_paid=Coalesce(Subquery(paid, output_field=MONEY), zero),
    ).annotate(balance=ExpressionWrapper(F("total_charged") - F("total_paid"), output_field=MONEY))


def _total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


class AccountView(APIView):
    """A student's statement. Admins pass ?student=<id> to view anyone's."""

    permission_classes = [StudentOrRequires("finance.view")]

    def get(self, request):
        student = resolve_student(request)
        summary = account_summary(student)
        return Response(
            {
                "student": {
                    "id": student.id,
                    "full_name": student.get_full_name(),
                    "university_id": student.university_id,
                    "email": student.email,
                    "avatar_url": student.avatar_url,
                },
                **{key: summary[key] for key in ("total_charged", "total_paid", "balance", "overdue", "next_due_date")},
                "charges": ChargeSerializer(summary["charges"], many=True).data,
                "payments": PaymentSerializer(summary["payments"], many=True).data,
            }
        )


class InvoiceView(APIView):
    """PDF invoice for one semester (?semester=<id>, or ?semester=none for charges without a semester)."""

    permission_classes = [StudentOrRequires("finance.view")]

    def get(self, request):
        student = resolve_student(request)
        semester_param = request.query_params.get("semester")
        semester = None if semester_param == "none" else get_object_or_404(Semester, pk=semester_param)
        if not Charge.objects.filter(student=student, semester=semester).exists():
            raise ValidationError("There are no charges to invoice for this semester.")
        return pdf_response(invoice_pdf(student, semester), f"{invoice_number(student, semester)}.pdf", request)


class StudentAccountsView(ListAPIView):
    """Admin: every student's balance. ?balance=outstanding|clear filters the list."""

    permission_classes = [Requires("finance.view")]
    serializer_class = StudentBalanceSerializer
    search_fields = ["first_name", "last_name", "university_id", "email"]
    ordering_fields = ["last_name", "balance", "total_charged", "total_paid"]
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        qs = with_balances(User.objects.filter(role=User.Role.STUDENT))
        balance_filter = self.request.query_params.get("balance")
        if balance_filter == "outstanding":
            qs = qs.filter(balance__gt=0)
        elif balance_filter == "clear":
            qs = qs.filter(balance__lte=0)
        return qs


class FinanceSummaryView(APIView):
    """Admin: bursary-wide totals for the Fees & Payments overview."""

    permission_classes = [Requires("finance.view")]

    def get(self, request):
        owing = with_balances(User.objects.filter(role=User.Role.STUDENT)).filter(balance__gt=0)
        completed = Payment.objects.filter(status=Payment.Status.COMPLETED)
        return Response(
            {
                "total_billed": _total(Charge.objects.all()),
                "total_collected": _total(completed),
                "outstanding": _total(owing, "balance"),
                "students_with_balance": owing.count(),
                "pending_proofs": PaymentProof.objects.filter(status=PaymentProof.Status.PENDING).count(),
                "collected_today": _total(completed.filter(paid_at__date=timezone.localdate())),
            }
        )
