from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("applications", views.ApplicationViewSet, basename="application")
router.register("cycles", views.CycleViewSet)

urlpatterns = [
    path("cycle/", views.CurrentCycleView.as_view(), name="admission-cycle"),
    path("register/", views.SignupView.as_view(), name="applicant-signup"),
    path("me/", views.MyApplicationView.as_view(), name="my-application"),
    path("me/documents/", views.MyDocumentsView.as_view(), name="my-documents"),
    path("me/documents/<int:pk>/", views.MyDocumentDetailView.as_view(), name="my-document"),
    path("me/pay/", views.MyPaymentView.as_view(), name="my-payment"),
    path("me/pay/verify/", views.MyPaymentVerifyView.as_view(), name="my-payment-verify"),
    path("me/submit/", views.MySubmitView.as_view(), name="my-submit"),
    path("me/accept/", views.MyAcceptView.as_view(), name="my-accept"),
    path("me/letter/", views.MyLetterView.as_view(), name="my-letter"),
    path("me/receipt/", views.MyReceiptView.as_view(), name="my-receipt"),
    path("documents/<int:pk>/file/", views.DocumentFileView.as_view(), name="document-file"),
    path("documents/<int:pk>/review/", views.DocumentReviewView.as_view(), name="document-review"),
    *router.urls,
]
