from contextlib import suppress

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudent
from apps.admissions import payments as admission_payments
from apps.admissions.models import ApplicationPayment

from .. import paystack
from ..models import GatewayTransaction
from ..serializers import OnlinePaymentSerializer, PaymentSerializer


def payment_gateway():
    """The online checkout: every online payment goes through Paystack. None when it isn't configured."""
    return "paystack" if paystack.is_configured() else None


class PaymentConfigView(APIView):
    """How students can pay: the online gateway and, if configured, the bursary bank account."""

    def get(self, request):
        bank = None
        if settings.BURSARY_ACCOUNT_NUMBER:
            bank = {
                "bank_name": settings.BURSARY_BANK_NAME,
                "account_name": settings.BURSARY_ACCOUNT_NAME,
                "account_number": settings.BURSARY_ACCOUNT_NUMBER,
            }
        return Response({"gateway": payment_gateway(), "bank_account": bank})


class PaystackInitializeView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        if not paystack.is_configured():
            raise ValidationError("Online payments are not available right now.")
        if not request.user.email:
            raise ValidationError("Add an email address to your profile before paying online.")
        serializer = OnlinePaymentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        callback_url = settings.PAYSTACK_CALLBACK_URL or request.build_absolute_uri("/portal/fees/paystack/callback")
        amount = serializer.validated_data["amount"]
        try:
            txn, authorization_url = paystack.initialize(request.user, amount, callback_url)
        except paystack.PaystackError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"reference": txn.reference, "authorization_url": authorization_url})


class PaystackVerifyView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        reference = str(request.data.get("reference", ""))
        txn = get_object_or_404(GatewayTransaction, reference=reference, student=request.user)
        if not txn.payment:
            try:
                txn = paystack.verify(reference)
            except paystack.PaystackError as exc:
                raise ValidationError(str(exc)) from exc
        return Response(
            {
                "status": txn.status,
                "message": txn.gateway_response,
                "payment": PaymentSerializer(txn.payment).data if txn.payment else None,
            }
        )


class PaystackWebhookView(APIView):
    """Paystack calls this for every event. Set its URL in the Paystack dashboard."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not paystack.is_configured() or not paystack.valid_signature(request.body, signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        event = request.data
        data = event.get("data") or {}
        reference = data.get("reference", "")
        if event.get("event") != "charge.success":
            return Response(status=status.HTTP_200_OK)
        # One Paystack account, one webhook: application fees (APP-…) belong to admissions.
        if reference.startswith(admission_payments.PREFIX):
            if ApplicationPayment.objects.filter(reference=reference).exists():
                admission_payments.record_success(reference, data)
        elif GatewayTransaction.objects.filter(reference=reference).exists():
            # A mismatch is already marked failed on the transaction; nothing for Paystack to retry.
            with suppress(paystack.PaystackError):
                paystack.record_success(reference, data)
        return Response(status=status.HTTP_200_OK)
