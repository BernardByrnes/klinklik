from django.urls import path

from application.reception.views import (
    AppointmentNoShowCheckInView,
    ArrivalEnquiryView,
    PatientCheckInSummaryView,
    PatientRegisterView,
    ReferralSourceView,
    VisitCancelErrorView,
    VisitCloseLwbsView,
    VisitCloseView,
    VisitCheckInView,
    VisitContextView,
)


urlpatterns = [
    path("patients/register/", PatientRegisterView.as_view(), name="patient_register"),
    path("patients/<uuid:pk>/check-in-summary/", PatientCheckInSummaryView.as_view(), name="patient_check_in_summary"),
    path("visits/check-in/", VisitCheckInView.as_view(), name="visit_check_in"),
    path(
        "appointments/<uuid:pk>/no-show-check-in/",
        AppointmentNoShowCheckInView.as_view(),
        name="appointment_no_show_check_in",
    ),
    path("visits/<uuid:pk>/", VisitContextView.as_view(), name="visit_context"),
    path("visits/<uuid:pk>/context/", VisitContextView.as_view(), name="visit_context_explicit"),
    path("visits/<uuid:pk>/cancel-error/", VisitCancelErrorView.as_view(), name="visit_cancel_error"),
    path("visits/<uuid:pk>/close-lwbs/", VisitCloseLwbsView.as_view(), name="visit_close_lwbs"),
    path("visits/<uuid:pk>/close/", VisitCloseView.as_view(), name="visit_close"),
    path("arrival-enquiries/", ArrivalEnquiryView.as_view(), name="arrival_enquiry_record"),
    path(
        "visits/<uuid:pk>/referral-source/",
        ReferralSourceView.as_view(),
        name="visit_referral_source_record",
    ),
]
