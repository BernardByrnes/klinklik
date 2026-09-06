"""Model-free command contracts and adapters for S-02 QueueEntry workflows."""

from application.contracts import CommandSpec
from scheduling.queue import (
    assign,
    call_next_or_exact,
    cancel,
    change_priority,
    complete,
    expire_sweep,
    hold,
    mark_ready_to_resume,
    no_response,
    requeue_same_entry,
    resume,
    start_service,
    takeover,
    transfer,
)


CMD_013_SPEC = CommandSpec(
    operation_id="CMD-013",
    rank1_id="QUE-003",
    capability="queue.call",
    owner_service="scheduling.queue.call_next_or_exact",
    lock_plan=("QueueEntry",),
)
CMD_014_SPEC = CommandSpec(
    operation_id="CMD-014",
    rank1_id="QUE-003",
    capability="queue.start_service",
    owner_service="scheduling.queue.start_service",
    lock_plan=("Visit", "QueueEntry"),
    requires_idempotency=False,
)
CMD_015_SPEC = CommandSpec(
    operation_id="CMD-015",
    rank1_id="QUE-004",
    capability="queue.assign",
    owner_service="scheduling.queue.assign",
    lock_plan=("QueueEntry",),
)
CMD_016_SPEC = CommandSpec(
    operation_id="CMD-016",
    rank1_id="QUE-006",
    capability="queue.hold",
    owner_service="scheduling.queue.hold",
    lock_plan=("QueueEntry",),
    requires_idempotency=False,
)
CMD_017_SPEC = CommandSpec(
    operation_id="CMD-017",
    rank1_id="QUE-006",
    capability="queue.resume",
    owner_service="scheduling.queue.resume",
    lock_plan=("QueueEntry",),
    requires_idempotency=False,
)
CMD_018_SPEC = CommandSpec(
    operation_id="CMD-018",
    rank1_id="QUE-005",
    capability="queue.transfer",
    owner_service="scheduling.queue.transfer",
    lock_plan=("Department", "Visit", "QueueEntry", "NumberSequence"),
)
CMD_019_SPEC = CommandSpec(
    operation_id="CMD-019",
    rank1_id="QUE-005",
    capability="queue.complete",
    owner_service="scheduling.queue.complete",
    lock_plan=("Visit", "QueueEntry"),
    requires_idempotency=False,
)
CMD_020_SPEC = CommandSpec(
    operation_id="CMD-020",
    rank1_id="QUE-009",
    capability="queue.no_response",
    owner_service="scheduling.queue.no_response",
    lock_plan=("FacilityWorkflowPolicy", "QueueEntry"),
)
CMD_021_SPEC = CommandSpec(
    operation_id="CMD-021",
    rank1_id="QUE-009",
    capability="queue.requeue",
    owner_service="scheduling.queue.requeue_same_entry",
    lock_plan=("Visit", "QueueEntry"),
)
CMD_022_SPEC = CommandSpec(
    operation_id="CMD-022",
    rank1_id="QUE-007",
    capability="queue.cancel",
    owner_service="scheduling.queue.cancel",
    lock_plan=("QueueEntry",),
)
CMD_023_SPEC = CommandSpec(
    operation_id="CMD-023",
    rank1_id="QUE-013",
    capability="queue.takeover",
    owner_service="scheduling.queue.takeover",
    lock_plan=("QueueEntry",),
)
CMD_024_SPEC = CommandSpec(
    operation_id="CMD-024",
    rank1_id="QUE-016",
    capability="queue.expire_sweep",
    owner_service="scheduling.queue.expire_sweep",
    lock_plan=("Visit", "QueueEntry"),
)
CMD_127_SPEC = CommandSpec(
    operation_id="CMD-127",
    rank1_id="QUE-008",
    capability="queue.priority_change",
    owner_service="scheduling.queue.change_priority",
    lock_plan=("Visit", "QueueEntry"),
)


COMMAND_SPECS = {
    spec.operation_id: spec
    for spec in (
        CMD_013_SPEC,
        CMD_014_SPEC,
        CMD_015_SPEC,
        CMD_016_SPEC,
        CMD_017_SPEC,
        CMD_018_SPEC,
        CMD_019_SPEC,
        CMD_020_SPEC,
        CMD_021_SPEC,
        CMD_022_SPEC,
        CMD_023_SPEC,
        CMD_024_SPEC,
        CMD_127_SPEC,
    )
}


# These thin adapters keep the application owner explicit while leaving all
# mutable state, locks, and transitions in scheduling.queue.
queue_call = call_next_or_exact
queue_start_service = start_service
queue_assign = assign
queue_hold = hold
queue_resume = resume
queue_transfer = transfer
queue_complete = complete
queue_no_response = no_response
queue_requeue = requeue_same_entry
queue_cancel = cancel
queue_takeover = takeover
system_queue_expire_sweep = expire_sweep
queue_priority_change = change_priority


__all__ = [
    "COMMAND_SPECS",
    "CMD_013_SPEC",
    "CMD_014_SPEC",
    "CMD_015_SPEC",
    "CMD_016_SPEC",
    "CMD_017_SPEC",
    "CMD_018_SPEC",
    "CMD_019_SPEC",
    "CMD_020_SPEC",
    "CMD_021_SPEC",
    "CMD_022_SPEC",
    "CMD_023_SPEC",
    "CMD_024_SPEC",
    "CMD_127_SPEC",
    "queue_call",
    "queue_start_service",
    "queue_assign",
    "queue_hold",
    "queue_resume",
    "queue_transfer",
    "queue_complete",
    "queue_no_response",
    "queue_requeue",
    "queue_cancel",
    "queue_takeover",
    "system_queue_expire_sweep",
    "queue_priority_change",
]
