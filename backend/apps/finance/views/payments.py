from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrRequires, Requires, StudentOrRequires

from ..documents import receipt_pdf
from ..models import STUDENT_SEARCH_FIELDS, Charge, FeeType, Payment
from ..serializers import (
    ChargeSerializer,
    FeeTypeSerializer,
    PaymentSerializer,
    RecordPaymentSerializer,
    VoidPaymentSerializer,
)
from ..services import record_payment, void_payment
from .common import owned_by_user, pdf_response


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Payment history. Admins record payments here; students normally pay through Paystack."""

    serializer_class = PaymentSerializer
    permission_classes = [StudentOrRequires("finance.view")]
    filterset_fields = ["student", "method", "status"]
    search_fields = ["receipt_number", "reference", *STUDENT_SEARCH_FIELDS]

    def get_queryset(self):
        return owned_by_user(Payment.objects.select_related("student", "recorded_by"), self.request.user)

    def create(self, request, *args, **kwargs):
        """The Bursary records offline payments (cash, POS, bank). Online payments only come from Paystack."""
        if not request.user.has_permission("finance.manage"):
            raise PermissionDenied("Online payments are made through Paystack. Use Pay online on the Fees page.")
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = record_payment(**serializer.validated_data, recorded_by=request.user)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        payment = self.get_object()
        return pdf_response(receipt_pdf(payment), f"{payment.receipt_number}.pdf", request)

    @action(detail=True, methods=["post"], permission_classes=[Requires("finance.manage")])
    def void(self, request, pk=None):
        serializer = VoidPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = void_payment(self.get_object(), serializer.validated_data["reason"].strip())
        return Response(PaymentSerializer(payment).data)


class ChargeViewSet(viewsets.ModelViewSet):
    """Charges on student accounts. Admins add manual ones; tuition and mandatory fees are automatic."""

    serializer_class = ChargeSerializer
    filterset_fields = ["student", "semester", "category"]

    def get_queryset(self):
        return owned_by_user(Charge.objects.select_related("student", "semester"), self.request.user)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [Requires("finance.manage")()]
        return [StudentOrRequires("finance.view")()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @staticmethod
    def _ensure_manual(charge):
        if charge.is_automatic:
            raise ValidationError(
                "Tuition and mandatory fees are calculated from enrollment and can't be edited directly."
            )

    def perform_update(self, serializer):
        self._ensure_manual(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_manual(instance)
        instance.delete()


class FeeTypeViewSet(viewsets.ModelViewSet):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = [ReadOnlyOrRequires("finance.manage")]
    pagination_class = None
