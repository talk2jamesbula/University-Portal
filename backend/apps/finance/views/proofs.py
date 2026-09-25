from django.http import FileResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import IsStudent, Requires, StudentOrRequires

from ..models import STUDENT_SEARCH_FIELDS, PaymentProof
from ..notifications import proof_submitted
from ..serializers import (
    ApproveProofSerializer,
    PaymentProofCreateSerializer,
    PaymentProofSerializer,
    RejectProofSerializer,
)
from ..services import approve_proof, reject_proof
from .common import owned_by_user


class PaymentProofViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Students upload proof of offline payments; the bursary approves or rejects them."""

    serializer_class = PaymentProofSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "student", "method"]
    search_fields = ["reference", "bank_name", *STUDENT_SEARCH_FIELDS]
    ordering_fields = ["submitted_at", "amount", "payment_date"]

    def get_queryset(self):
        qs = PaymentProof.objects.select_related("student", "reviewed_by", "payment")
        return owned_by_user(qs, self.request.user)

    def get_permissions(self):
        if self.action == "create":
            return [IsStudent()]
        if self.action in ("approve", "reject"):
            return [Requires("finance.manage")()]
        return [StudentOrRequires("finance.view")()]

    def create(self, request, *args, **kwargs):
        serializer = PaymentProofCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proof = serializer.save(student=request.user)
        proof_submitted(proof)
        return Response(PaymentProofSerializer(proof).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, proof):
        # Students may withdraw a proof that hasn't been reviewed yet. The file is removed by a signal.
        if not self.request.user.is_student or proof.status != PaymentProof.Status.PENDING:
            raise ValidationError("Only a pending proof can be withdrawn, and only by the student.")
        proof.delete()

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        proof = self.get_object()
        return FileResponse(proof.file.open("rb"), content_type=proof.content_type, filename=proof.original_filename)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = ApproveProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proof = approve_proof(
            self.get_object().pk,
            request.user,
            amount=serializer.validated_data.get("amount"),
            note=serializer.validated_data["note"].strip(),
        )
        return Response(PaymentProofSerializer(proof).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = RejectProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proof = reject_proof(self.get_object().pk, request.user, serializer.validated_data["reason"].strip())
        return Response(PaymentProofSerializer(proof).data)
