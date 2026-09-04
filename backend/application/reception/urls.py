from django.urls import path

from application.reception.views import (
    ArrivalEnquiryView,
    PatientRegisterView,
    ReferralSourceView,
    VisitCancelErrorView,
    VisitCheckInView,
    VisitContextView,
)


urlpatterns = [
    path("patients/register/", PatientRegisterView.as_view(), name="patient_register"),
    path("visits/check-in/", VisitCheckInView.as_view(), name="visit_check_in"),
    path("visits/<uuid:pk>/", VisitContextView.as_view(), name="visit_context"),
    path("visits/<uuid:pk>/context/", VisitContextView.as_view(), name="visit_context_explicit"),
    path("visits/<uuid:pk>/cancel-error/", VisitCancelErrorView.as_view(), name="visit_cancel_error"),
    path("arrival-enquiries/", ArrivalEnquiryView.as_view(), name="arrival_enquiry_record"),
    path(
        "visits/<uuid:pk>/referral-source/",
        ReferralSourceView.as_view(),
        name="visit_referral_source_record",
    ),
]
