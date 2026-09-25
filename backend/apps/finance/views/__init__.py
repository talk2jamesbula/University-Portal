"""Finance API, split by area:

- accounts:  statements, invoices and bursary reports
- payments:  payments, charges and fee types
- gateway:   Paystack checkout, verification and webhook
- proofs:    uploaded proofs of offline payment
"""

from .accounts import AccountView, FinanceSummaryView, InvoiceView, StudentAccountsView
from .gateway import PaymentConfigView, PaystackInitializeView, PaystackVerifyView, PaystackWebhookView
from .payments import ChargeViewSet, FeeTypeViewSet, PaymentViewSet
from .proofs import PaymentProofViewSet

__all__ = [
    "AccountView",
    "ChargeViewSet",
    "FeeTypeViewSet",
    "FinanceSummaryView",
    "InvoiceView",
    "PaymentConfigView",
    "PaymentProofViewSet",
    "PaymentViewSet",
    "PaystackInitializeView",
    "PaystackVerifyView",
    "PaystackWebhookView",
    "StudentAccountsView",
]
