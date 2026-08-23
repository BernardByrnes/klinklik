from django.urls import include, path

from clinical.views import (
    EncounterAllergyReviewView,
    PatientAllergyEnteredInErrorView,
    PatientAllergyStatusView,
    PatientAllergyView,
    EncounterAmendView,
    EncounterDetailView,
    EncounterListCreateView,
    EncounterNoteView,
    EncounterSignView,
    TriageView,
)


urlpatterns = [
    path("", include("scheduling.urls")),
    path("triage/<uuid:queue_id>/", TriageView.as_view(), name="triage"),
    path("encounters/", EncounterListCreateView.as_view(), name="encounter-create"),
    path("encounters/<uuid:pk>/", EncounterDetailView.as_view(), name="encounter-detail"),
    path("encounters/<uuid:pk>/notes/", EncounterNoteView.as_view(), name="encounter-note"),
    path("encounters/<uuid:pk>/sign/", EncounterSignView.as_view(), name="encounter-sign"),
    path("encounters/<uuid:pk>/amend/", EncounterAmendView.as_view(), name="encounter-amend"),
    path("patients/<uuid:patient_id>/allergies/", PatientAllergyView.as_view(), name="patient-allergy-add"),
    path("patients/<uuid:patient_id>/allergy-status/", PatientAllergyStatusView.as_view(), name="patient-allergy-status"),
    path("patients/<uuid:patient_id>/allergies/<uuid:allergy_id>/entered-in-error/", PatientAllergyEnteredInErrorView.as_view(), name="patient-allergy-entered-in-error"),
    path("encounters/<uuid:pk>/allergies/review/", EncounterAllergyReviewView.as_view(), name="encounter-allergy-review"),
]
