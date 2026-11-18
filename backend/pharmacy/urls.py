from django.urls import path

from pharmacy.views import (
    DispenseConfirmView,
    DispenseDetailView,
    DispensePrepareView,
    OTCSaleCreateView,
    OTCSaleListView,
    PrescriptionCancelView,
    PrescriptionClaimView,
    PrescriptionDraftView,
    PrescriptionItemNotDispensedView,
    PrescriptionQueueView,
    ProductInstructionTemplateView,
)

urlpatterns = [
    path("queue/", PrescriptionQueueView.as_view(), name="pharmacy-queue"),
    path(
        "prescriptions/draft/",
        PrescriptionDraftView.as_view(),
        name="pharmacy-prescription-draft",
    ),
    path(
        "prescriptions/<uuid:pk>/claim/",
        PrescriptionClaimView.as_view(),
        name="pharmacy-prescription-claim",
    ),
    path(
        "prescriptions/<uuid:pk>/cancel/",
        PrescriptionCancelView.as_view(),
        name="pharmacy-prescription-cancel",
    ),
    path(
        "prescriptions/<uuid:prescription_id>/dispenses/",
        DispensePrepareView.as_view(),
        name="pharmacy-dispense-prepare",
    ),
    path(
        "dispenses/<uuid:pk>/",
        DispenseDetailView.as_view(),
        name="pharmacy-dispense-detail",
    ),
    path(
        "dispenses/<uuid:pk>/confirm/",
        DispenseConfirmView.as_view(),
        name="pharmacy-dispense-confirm",
    ),
    path(
        "items/<uuid:item_id>/not-dispensed/",
        PrescriptionItemNotDispensedView.as_view(),
        name="pharmacy-item-not-dispensed",
    ),
    path(
        "products/<uuid:pk>/instruction-template/",
        ProductInstructionTemplateView.as_view(),
        name="pharmacy-product-instruction-template",
    ),
    path("otc/", OTCSaleCreateView.as_view(), name="pharmacy-otc-create"),
    path("otc/sales/", OTCSaleListView.as_view(), name="pharmacy-otc-list"),
]
