from audit.models import AuditEvent
from core.services import request_id, safe_user_agent


def record_event(
    *,
    request=None,
    organisation,
    actor=None,
    action,
    entity_type,
    entity_id,
    facility=None,
    before=None,
    after=None,
    reason="",
):
    ip_address = None
    rid = ""
    agent = ""
    if request is not None:
        rid = request_id(request)
        agent = safe_user_agent(request)
        ip_address = request.META.get("REMOTE_ADDR")
    return AuditEvent.objects.create(
        organisation=organisation,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        facility=facility,
        request_id=rid,
        ip_address=ip_address,
        user_agent=agent,
        before=before,
        after=after,
        reason=reason,
    )
