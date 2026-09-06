"""Canonical queue routes, kept as a discoverable application boundary."""

from django.urls import path

from application.queue.views import (
    OperationalQueueProjectionView,
    PublicBoardProjectionView,
    QueueAssignView,
    QueueCallView,
    QueueCancelView,
    QueueExpireSweepView,
    QueueHistoryProjectionView,
    QueueLocationProjectionView,
    QueueNoResponseView,
    QueuePriorityProjectionView,
    QueuePriorityView,
    QueueRequeueView,
    QueueTakeoverView,
    QueueTransferView,
    SupervisorQueueProjectionView,
)


urlpatterns = [
    path("queue/operational/", OperationalQueueProjectionView.as_view(), name="queue-operational-projection"),
    path("queue/priority-projection/", QueuePriorityProjectionView.as_view(), name="queue-priority-projection"),
    path("queue/location/<uuid:visit_id>/", QueueLocationProjectionView.as_view(), name="queue-location-projection"),
    path("queue/history/<uuid:visit_id>/", QueueHistoryProjectionView.as_view(), name="queue-history-projection"),
    path("queue/supervisor/", SupervisorQueueProjectionView.as_view(), name="queue-supervisor-projection"),
    path("queue/board/", PublicBoardProjectionView.as_view(), name="queue-public-board-projection"),
    path("queue/call/", QueueCallView.as_view(operation_id="queueCall"), name="queue-call"),
    path("queue/call-next/", QueueCallView.as_view(operation_id="queueCallNext"), name="queue-call-next"),
    path("queue/assign/", QueueAssignView.as_view(operation_id="queueAssign"), name="queue-assign"),
    path("queue/transfer/", QueueTransferView.as_view(operation_id="queueTransfer"), name="queue-transfer"),
    path("queue/priority/", QueuePriorityView.as_view(operation_id="queuePriorityChange"), name="queue-priority-change"),
    path("queue/no-response/", QueueNoResponseView.as_view(operation_id="queueNoResponse"), name="queue-no-response"),
    path("queue/requeue/", QueueRequeueView.as_view(operation_id="queueRequeue"), name="queue-requeue"),
    path("queue/cancel/", QueueCancelView.as_view(operation_id="queueCancel"), name="queue-cancel"),
    path("queue/takeover/", QueueTakeoverView.as_view(operation_id="queueTakeover"), name="queue-takeover"),
    path("queue/expire-sweep/", QueueExpireSweepView.as_view(operation_id="systemQueueExpireSweep"), name="queue-expire-sweep"),
    path("queue/<uuid:pk>/call/", QueueCallView.as_view(operation_id="queueExactCall"), name="queue-exact-call"),
    path("queue/<uuid:pk>/assign/", QueueAssignView.as_view(operation_id="queueEntryAssign"), name="queue-entry-assign"),
    path("queue/<uuid:pk>/priority/", QueuePriorityView.as_view(operation_id="queueEntryPriorityChange"), name="queue-entry-priority-change"),
    path("queue/<uuid:pk>/no-response/", QueueNoResponseView.as_view(operation_id="queueEntryNoResponse"), name="queue-entry-no-response"),
    path("queue/<uuid:pk>/requeue/", QueueRequeueView.as_view(operation_id="queueEntryRequeue"), name="queue-entry-requeue"),
    path("queue/<uuid:pk>/cancel/", QueueCancelView.as_view(operation_id="queueEntryCancel"), name="queue-entry-cancel"),
    path("queue/<uuid:pk>/takeover/", QueueTakeoverView.as_view(operation_id="queueEntryTakeover"), name="queue-entry-takeover"),
    path("queue/<uuid:pk>/transfer/", QueueTransferView.as_view(operation_id="queueEntryTransfer"), name="queue-entry-transfer"),
]
