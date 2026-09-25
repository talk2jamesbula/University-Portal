from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountView,
    ChargeViewSet,
    FeeTypeViewSet,
    FinanceSummaryView,
    InvoiceView,
    PaymentConfigView,
    PaymentProofViewSet,
    PaymentViewSet,
    PaystackInitializeView,
    PaystackVerifyView,
    PaystackWebhookView,
    StudentAccountsView,
)

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("charges", ChargeViewSet, basename="charge")
router.register("fee-types", FeeTypeViewSet, basename="fee-type")
router.register("payment-proofs", PaymentProofViewSet, basename="payment-proof")

urlpatterns = [
    path("account/", AccountView.as_view(), name="finance-account"),
    path("accounts/", StudentAccountsView.as_view(), name="finance-accounts"),
    path("summary/", FinanceSummaryView.as_view(), name="finance-summary"),
    path("invoice/", InvoiceView.as_view(), name="finance-invoice"),
    path("payment-config/", PaymentConfigView.as_view(), name="payment-config"),
    path("paystack/initialize/", PaystackInitializeView.as_view(), name="paystack-initialize"),
    path("paystack/verify/", PaystackVerifyView.as_view(), name="paystack-verify"),
    path("paystack/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),
    *router.urls,
]
