from uuid import uuid4
"""S-24 attached audit-code evidence (one-field additions to existing writers)."""

from pathlib import Path

import pytest

from audit.models import AuditEvent
from core.services import tenant_atomic
from tests.test_s05_billing import register

pytestmark = pytest.mark.django_db

ATTACHED = {
    "CLINICAL_NOTE_AMENDED": "backend/clinical/services.py",
    "ALLERGY_RECORDED": "backend/clinical/allergies.py",
    "ALLERGY_STATUS_SET": "backend/clinical/allergies.py",
    "ALLERGY_ENTERED_ERROR": "backend/clinical/allergies.py",
    "ALLERGY_REVIEWED": "backend/clinical/allergies.py",
    "DIAGNOSIS_SAVED": "backend/clinical/diagnoses.py",
    "DISPOSITION_SET": "backend/clinical/dispositions.py",
    "FOLLOWUP_RECORDED": "backend/clinical/followups.py",
}
ROOT = Path(__file__).resolve().parents[2]


def test_s24_each_attached_code_sits_on_an_existing_audit_writer():
    for code, relative in ATTACHED.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        marker = f'event_code="{code}"'
        assert marker in source, (code, relative)
        index = source.index(marker)
        call = source[max(0, index - 500):index]
        assert "record_event(" in call and "entity_id=" in call, code


def test_s24_allergy_record_emits_declared_code_with_actor_and_entity(
    tenant, authed_client
):
    patient_id = register(authed_client, f"s24-allergy-{uuid4().hex}")
    response = authed_client.post(
        f"/api/v1/clinic/patients/{patient_id}/allergies/",
        {"substance": "Synthetic S24 latex", "reaction": "rash", "severity": "MILD"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s24-allergy-{uuid4().hex}",
    )
    assert response.status_code == 201, response.data
    with tenant_atomic(tenant.organisation.id):
        event = AuditEvent.objects.get(event_code="ALLERGY_RECORDED")
        assert str(event.actor_id) == str(tenant.user.id)
        assert event.entity_type == "Allergy"
        assert event.entity_id
