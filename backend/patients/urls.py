from django.urls import path

from patients.views import PatientDetailView, PatientLinkView, PatientListCreateView


urlpatterns = [
    path("", PatientListCreateView.as_view(), name="patient-list-create"),
    path("<uuid:pk>/", PatientDetailView.as_view(), name="patient-detail"),
    path("<uuid:pk>/link/", PatientLinkView.as_view(), name="patient-link"),
]
