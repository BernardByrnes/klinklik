from django.urls import path

from billing.views import (
    InvoiceByVisitView,
    InvoiceCanonicalPaymentView,
    InvoiceDetailView,
    InvoiceLineCreateView,
    InvoiceLineVoidView,
    InvoiceListCreateView,
    InvoicePaymentView,
    InvoiceReceiptView,
    PaymentMethodListView,
    PaymentReverseView,
    ReceiptByNumberView,
    ReceiptDetailView,
    ReceiptReprintView,
    ServiceCatalogView,
    ShiftCloseView,
    ShiftCurrentView,
    ShiftOpenView,
)


urlpatterns = [
    path("services/", ServiceCatalogView.as_view(), name="service-catalog"),
    path("invoices/", InvoiceListCreateView.as_view(), name="invoice-list-create"),
    path("invoices/by-visit/<uuid:visit_id>/", InvoiceByVisitView.as_view(), name="invoice-by-visit"),
    path("invoices/<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/<uuid:pk>/pay/", InvoicePaymentView.as_view(), name="invoice-pay"),
    path("invoices/<uuid:pk>/payments/", InvoiceCanonicalPaymentView.as_view(), name="invoice-payment-create"),
    path("invoices/<uuid:pk>/receipt/", InvoiceReceiptView.as_view(), name="invoice-receipt"),
    path("invoices/<uuid:pk>/lines/", InvoiceLineCreateView.as_view(), name="invoice-line-create"),
    path(
        "invoices/<uuid:pk>/lines/<uuid:line_id>/void/",
        InvoiceLineVoidView.as_view(),
        name="invoice-line-void",
    ),
    path("payments/<uuid:pk>/reverse/", PaymentReverseView.as_view(), name="payment-reverse"),
    path("receipts/<uuid:pk>/", ReceiptDetailView.as_view(), name="receipt-detail"),
    path("receipts/<uuid:pk>/reprint/", ReceiptReprintView.as_view(), name="receipt-reprint"),
    path(
        "receipts/by-number/<str:receipt_no>/",
        ReceiptByNumberView.as_view(),
        name="receipt-by-number",
    ),
    path("shifts/open/", ShiftOpenView.as_view(), name="shift-open"),
    path("shifts/current/", ShiftCurrentView.as_view(), name="shift-current"),
    path("shifts/<uuid:pk>/close/", ShiftCloseView.as_view(), name="shift-close"),
    path("payment-methods/", PaymentMethodListView.as_view(), name="payment-methods"),
]
