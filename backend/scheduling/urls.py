from django.urls import include, path
from scheduling.views import CheckInView, QueueClaimView, QueueListView


urlpatterns = [
    path("check-ins/", CheckInView.as_view(), name="check-in"),
    path("queue/", QueueListView.as_view(), name="queue-list"),
    path("", include("application.queue.urls")),
    path("queue/<uuid:pk>/claim/", QueueClaimView.as_view(), name="queue-claim"),
]
