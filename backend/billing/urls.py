from django.urls import path

from billing.views import (
    InvoiceDetailView,
    InvoiceListCreateView,
    InvoicePaymentView,
    InvoiceReceiptView,
    ServiceCatalogView,
)


urlpatterns = [
    path("services/", ServiceCatalogView.as_view(), name="service-catalog"),
    path("invoices/", InvoiceListCreateView.as_view(), name="invoice-list-create"),
    path("invoices/<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/<uuid:pk>/pay/", InvoicePaymentView.as_view(), name="invoice-pay"),
    path("invoices/<uuid:pk>/receipt/", InvoiceReceiptView.as_view(), name="invoice-receipt"),
]
