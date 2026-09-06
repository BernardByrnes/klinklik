"""Application-owned names for scheduling's read-only queue projections."""

from scheduling.operational_queries import (
    get_operational_queue_projection,
    get_public_board_projection,
    get_queue_history_projection,
    get_queue_location_projection,
    get_supervisor_queue_projection,
    operational_queue_projection,
    public_board_projection,
    queue_history_projection,
    queue_location_projection,
    queue_priority_projection,
    supervisor_queue_projection,
)

__all__ = [
    "get_operational_queue_projection",
    "get_public_board_projection",
    "get_queue_history_projection",
    "get_queue_location_projection",
    "get_supervisor_queue_projection",
    "operational_queue_projection",
    "public_board_projection",
    "queue_history_projection",
    "queue_location_projection",
    "queue_priority_projection",
    "supervisor_queue_projection",
]
