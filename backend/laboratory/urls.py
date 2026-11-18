from django.urls import path

from laboratory.views import (
    LabEncounterResultsView,
    LabItemCancelView,
    LabItemCollectView,
    LabItemRejectView,
    LabOrderCreateView,
    LabResultAmendView,
    LabResultReleaseView,
    LabResultSaveView,
    LabTestListCreateView,
    LabWorklistView,
)


urlpatterns = [
    path("tests/", LabTestListCreateView.as_view(), name="lab-tests"),
    path("orders/", LabOrderCreateView.as_view(), name="lab-orders"),
    path("worklist/", LabWorklistView.as_view(), name="lab-worklist"),
    path("items/<uuid:pk>/collect/", LabItemCollectView.as_view(), name="lab-item-collect"),
    path("items/<uuid:pk>/reject/", LabItemRejectView.as_view(), name="lab-item-reject"),
    path("items/<uuid:pk>/results/", LabResultSaveView.as_view(), name="lab-result-save"),
    path("items/<uuid:pk>/release/", LabResultReleaseView.as_view(), name="lab-result-release"),
    path("items/<uuid:pk>/amend/", LabResultAmendView.as_view(), name="lab-result-amend"),
    path("items/<uuid:pk>/cancel/", LabItemCancelView.as_view(), name="lab-item-cancel"),
    path(
        "encounters/<uuid:encounter_id>/results/",
        LabEncounterResultsView.as_view(),
        name="lab-encounter-results",
    ),
]
