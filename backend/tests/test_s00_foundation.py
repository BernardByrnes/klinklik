from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
import sys

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from application.contracts import CommandContext, CommandResult, CommandSpec
from application.runner import run_command
from audit.models import AuditEvent
from audit.services import DenialAuditConflict, record_event, record_fact, write_denial_audit
from core import services
from core.clock import KAMPALA, is_utc, local_service_date, now, require_aware
from core.errors import IdempotencyConflict, RetryableCommandFailure
from core.idempotency import (
    UncommittedResponse,
    execute_idempotent,
    key_hash,
)
from core.models import IdempotencyRecord
from core.rls import is_tenant_policy_expression
from core.services import tenant_atomic
from tenancy.models import FacilityWorkflowPolicy


pytestmark = pytest.mark.django_db(transaction=True)


def _execute(tenant, key, fingerprint, callback, operation="CMD-001"):
    with tenant_atomic(tenant.organisation.id):
        return execute_idempotent(
            organisation=tenant.organisation,
            operation=operation,
            key=key,
            fingerprint=fingerprint,
            callback=callback,
        )


def test_idempotency_claim_replay_conflict_and_no_raw_key(tenant):
    key = "s00-safe-key"
    fingerprint = "a" * 64
    first = _execute(
        tenant,
        key,
        fingerprint,
        lambda: CommandResult(
            status_code=201,
            body={"reference": "synthetic-1"},
            result_reference={
                "entity_type": "TechnicalProbe",
                "entity_id": "synthetic-1",
            },
        ),
    )
    assert first.replay is False

    record = IdempotencyRecord.objects.get(
        organisation=tenant.organisation,
        operation="CMD-001",
        key_hash=key_hash(key),
    )
    assert not hasattr(record, "key")
    assert key not in str(record.__dict__)
    assert record.completed_at is not None
    assert record.status_code == 201
    assert record.result_reference == {
        "entity_type": "TechnicalProbe",
        "entity_id": "synthetic-1",
    }

    replay = _execute(
        tenant,
        key,
        fingerprint,
        lambda: pytest.fail("a committed replay must not execute the callback"),
    )
    assert replay.replay is True
    assert replay.body == {"reference": "synthetic-1"}
    assert replay.result_reference == record.result_reference

    with pytest.raises(IdempotencyConflict):
        _execute(tenant, key, "b" * 64, lambda: CommandResult(status_code=201, body={}))


def test_failed_idempotent_response_rolls_back_claim(tenant):
    with pytest.raises(UncommittedResponse):
        _execute(
            tenant,
            "s00-failed-key",
            "c" * 64,
            lambda: CommandResult(status_code=400, body={"detail": "synthetic"}),
        )
    assert not IdempotencyRecord.objects.filter(
        organisation=tenant.organisation,
        operation="CMD-001",
        key_hash=key_hash("s00-failed-key"),
    ).exists()


def test_audit_fact_rolls_back_with_failed_command(tenant):
    with pytest.raises(RuntimeError):
        with tenant_atomic(tenant.organisation.id):
            record_fact(
                organisation=tenant.organisation,
                actor=tenant.user,
                event_code="S00_ROLLBACK",
                entity_type="TechnicalProbe",
                entity_id="synthetic-rollback",
                after={"state": "STARTED"},
            )
            raise RuntimeError("synthetic command failure")
    assert not AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="TechnicalProbe",
        entity_id="synthetic-rollback",
    ).exists()


def test_application_command_contract_runs_in_one_transaction(tenant):
    spec = CommandSpec(
        operation_id="CMD-001",
        rank1_id="REC-001",
        capability="patient.create",
        owner_service="patients.create",
        lock_plan=("Patient",),
    )
    context = CommandContext(
        organisation_id=tenant.organisation.id,
        actor_id=tenant.user.id,
        facility_id=tenant.facility.id,
        capability="patient.create",
        scope="tenant",
        idempotency_key="s00-command-key",
        fingerprint="d" * 64,
    )
    result = run_command(
        spec,
        context,
        lambda current: CommandResult(
            status_code=201,
            body={"organisation_id": str(current.organisation_id)},
        ),
    )
    assert result.status_code == 201
    assert result.body["organisation_id"] == str(tenant.organisation.id)


def test_non_success_command_result_rolls_back(tenant):
    spec = CommandSpec(
        operation_id="CMD-001",
        rank1_id="REC-001",
        capability="patient.create",
        owner_service="patients.create",
        lock_plan=("Patient",),
        requires_idempotency=False,
    )
    context = CommandContext(
        organisation_id=tenant.organisation.id,
        actor_id=tenant.user.id,
        facility_id=tenant.facility.id,
        capability="patient.create",
        scope="tenant",
    )
    with pytest.raises(UncommittedResponse):
        run_command(
            spec,
            context,
            lambda current: (
                record_fact(
                    organisation=tenant.organisation,
                    actor=tenant.user,
                    event_code="S00_NON_SUCCESS",
                    entity_type="TechnicalProbe",
                    entity_id="synthetic-non-success",
                    after={"state": "REJECTED"},
                ),
                CommandResult(status_code=409, body={"code": "CONFLICT"}),
            )[1],
        )
    assert not AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="TechnicalProbe",
        entity_id="synthetic-non-success",
    ).exists()


@pytest.mark.parametrize(
    ("attribute", "sqlstate"),
    [("sqlstate", "40001"), ("diag", "40P01")],
)
def test_psycopg3_retryable_sqlstates_retry_the_whole_command(monkeypatch, tenant, attribute, sqlstate):
    attempts = []

    @contextmanager
    def fake_tenant_atomic(_organisation_id):
        yield

    def callback():
        attempts.append(True)
        if len(attempts) == 1:
            error = DatabaseError("retryable PostgreSQL failure")
            if attribute == "diag":
                error.diag = SimpleNamespace(sqlstate=sqlstate)
            else:
                error.sqlstate = sqlstate
            raise error
        return "committed"

    monkeypatch.setattr(services, "tenant_atomic", fake_tenant_atomic)
    monkeypatch.setattr(services.connection, "vendor", "postgresql")
    assert services.run_in_tenant(tenant.organisation.id, callback) == "committed"
    assert len(attempts) == 2


@pytest.mark.parametrize(
    ("attribute", "sqlstate"),
    [("sqlstate", "40001"), ("diag", "40P01"), ("pgcode", "40001")],
)
def test_retryable_sqlstate_exhaustion_is_bounded_and_canonical(monkeypatch, tenant, attribute, sqlstate):
    attempts = []

    @contextmanager
    def fake_tenant_atomic(_organisation_id):
        yield

    def callback():
        attempts.append(True)
        error = DatabaseError("retryable PostgreSQL failure")
        if attribute == "diag":
            error.diag = SimpleNamespace(sqlstate=sqlstate)
        else:
            setattr(error, attribute, sqlstate)
        raise error

    monkeypatch.setattr(services, "tenant_atomic", fake_tenant_atomic)
    monkeypatch.setattr(services.connection, "vendor", "postgresql")
    with pytest.raises(RetryableCommandFailure):
        services.run_in_tenant(tenant.organisation.id, callback)
    assert len(attempts) == 3


def test_nonretryable_database_failure_is_not_retried(monkeypatch, tenant):
    attempts = []

    @contextmanager
    def fake_tenant_atomic(_organisation_id):
        yield

    def callback():
        attempts.append(True)
        error = DatabaseError("unique violation")
        error.sqlstate = "23505"
        raise error

    monkeypatch.setattr(services, "tenant_atomic", fake_tenant_atomic)
    monkeypatch.setattr(services.connection, "vendor", "postgresql")
    with pytest.raises(DatabaseError):
        services.run_in_tenant(tenant.organisation.id, callback)
    assert len(attempts) == 1


@pytest.mark.parametrize(
    "key",
    ["patientName", "PatientName", "diagnosis", "medicationName", "dateOfBirth", "freeText"],
)
def test_audit_phi_canaries_are_rejected_across_key_styles(tenant, key):
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(ValueError):
            record_fact(
                organisation=tenant.organisation,
                actor=tenant.user,
                event_code="S00_PHI_CANARY",
                entity_type="TechnicalProbe",
                entity_id="synthetic-phi",
                after={key: "Synthetic human-readable content"},
            )


def test_audit_identifier_values_require_opaque_references(tenant):
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(ValueError):
            record_fact(
                organisation=tenant.organisation,
                actor=tenant.user,
                event_code="S00_ID_CANARY",
                entity_type="TechnicalProbe",
                entity_id="synthetic-human-id",
                source_ids={"patient_id": "Alice Smith"},
            )
        event = record_fact(
            organisation=tenant.organisation,
            actor=tenant.user,
            event_code="S00_ID_CANARY",
            entity_type="TechnicalProbe",
            entity_id="synthetic-opaque-id",
            source_ids={"patientId": "opaque-patient-1"},
            after={"state": "READY", "noteType": "CONSULTATION"},
        )
    assert event.source_ids == {"patientId": "opaque-patient-1"}
    assert event.after == {"state": "READY", "noteType": "CONSULTATION"}


def test_compatibility_audit_event_uses_redacting_safe_metadata_path(tenant):
    with tenant_atomic(tenant.organisation.id):
        event = record_event(
            organisation=tenant.organisation,
            actor=tenant.user,
            facility=tenant.facility,
            action="UPDATE",
            event_code="S00_COMPAT_EVENT",
            entity_type="TechnicalProbe",
            entity_id="synthetic-compat",
            before={
                "patientName": "Alice Smith",
                "encounterId": "opaque-encounter-1",
                "state": "BEFORE",
            },
            after={
                "diagnosis": "Sensitive diagnosis",
                "medicationName": "Sensitive medication",
                "dateOfBirth": "2000-01-01",
                "freeText": "Clinical narrative",
                "patientId": "opaque-patient-1",
                "reason": "SAFE_EVENT",
                "state": "READY",
            },
            source_ids={
                "patient_id": "Alice Smith",
                "safe_ref": "opaque-reference-1",
                "testResult": "Sensitive result",
            },
            reason="Alice Smith supplied a clinical narrative",
            reason_code="SAFE_REASON",
        )
    payload = json.dumps(
        {
            "before": event.before,
            "after": event.after,
            "source_ids": event.source_ids,
            "reason": event.reason,
        },
        sort_keys=True,
    )
    assert "Alice Smith" not in payload
    assert "Sensitive diagnosis" not in payload
    assert "Sensitive medication" not in payload
    assert "Clinical narrative" not in payload
    assert event.before == {"encounterId": "opaque-encounter-1", "state": "BEFORE"}
    assert event.after == {
        "patientId": "opaque-patient-1",
        "reason": "SAFE_EVENT",
        "state": "READY",
    }
    assert event.source_ids == {"safe_ref": "opaque-reference-1"}
    assert event.reason == ""
    assert event.reason_code == "SAFE_REASON"


def test_rls_policy_expression_requires_exact_organisation_scope():
    accepted = [
        "organisation_id = current_setting('app.current_org_id')::uuid",
        "(organisation_id = (current_setting('app.current_org_id'::text))::uuid)",
        "organisation_id = current_setting('app.current_org_id', true)::uuid",
    ]
    rejected = [
        "organisation_id = current_setting('app.other_org_id')::uuid",
        "organisation_id = current_setting('app.current_org_id')::uuid OR true",
        "facility_id = current_setting('app.current_org_id')::uuid",
    ]
    assert all(is_tenant_policy_expression(expression) for expression in accepted)
    assert not any(is_tenant_policy_expression(expression) for expression in rejected)


def test_generated_api_contract_fingerprint_covers_material_schema_surface():
    from tools.generate_api_client import contract_fingerprint, render

    schema = {
        "paths": {
            "/patients/{id}": {
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    }
                ],
                "patch": {
                    "operationId": "patients.update",
                    "parameters": [
                        {
                            "name": "If-Match",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/PatientPatch",
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Patient"},
                                }
                            }
                        }
                    },
                },
            }
        },
        "components": {
            "schemas": {
                "PatientPatch": {
                    "type": "object",
                    "required": ["first_name", "status"],
                    "properties": {
                        "first_name": {"type": "string"},
                        "status": {"enum": ["ACTIVE", "ARCHIVED"]},
                    },
                },
                "Patient": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "string"}},
                },
            }
        },
    }
    original = contract_fingerprint(schema)
    changed_request = deepcopy(schema)
    changed_request["components"]["schemas"]["PatientPatch"]["required"].append("age")
    changed_response = deepcopy(schema)
    changed_response["components"]["schemas"]["Patient"]["properties"]["id"]["enum"] = ["P-1", "P-2"]
    changed_header = deepcopy(schema)
    changed_header["paths"]["/patients/{id}"]["patch"]["parameters"][0]["required"] = False
    assert contract_fingerprint(changed_request) != original
    assert contract_fingerprint(changed_response) != original
    assert contract_fingerprint(changed_header) != original
    reordered = deepcopy(schema)
    reordered["components"]["schemas"]["PatientPatch"]["required"] = ["status", "first_name"]
    reordered["components"]["schemas"]["PatientPatch"]["properties"]["status"]["enum"] = ["ARCHIVED", "ACTIVE"]
    assert contract_fingerprint(reordered) == original
    assert f'GENERATED_API_CONTRACT_SHA256 = "{original}"' in render(schema)


def test_clock_is_aware_utc_and_kampala_local():
    timestamp = now()
    assert is_utc(timestamp)
    assert local_service_date(timestamp) == timestamp.astimezone(KAMPALA).date()
    with pytest.raises(ValueError):
        require_aware(timestamp.replace(tzinfo=None))


def test_audit_fact_requires_transaction_and_rejects_sensitive_payload(tenant):
    with pytest.raises(RuntimeError):
        record_fact(
            organisation=tenant.organisation,
            actor=tenant.user,
            event_code="S00_FACT",
            entity_type="TechnicalProbe",
            entity_id="synthetic-1",
        )

    with tenant_atomic(tenant.organisation.id):
        event = record_fact(
            organisation=tenant.organisation,
            actor=tenant.user,
            facility=tenant.facility,
            event_code="S00_FACT",
            entity_type="TechnicalProbe",
            entity_id="synthetic-1",
            source_ids={"patient_id": "opaque-1"},
            after={"state": "READY"},
        )
        with pytest.raises(ValueError):
            record_fact(
                organisation=tenant.organisation,
                actor=tenant.user,
                event_code="S00_FACT",
                entity_type="TechnicalProbe",
                entity_id="synthetic-2",
                after={"patient_name": "Synthetic"},
            )
    assert event.source_ids == {"patient_id": "opaque-1"}
    assert AuditEvent.objects.filter(pk=event.pk).exists()


def test_denial_audit_is_idempotent_and_conflicts_on_different_fingerprint(tenant):
    kwargs = {
        "organisation": tenant.organisation,
        "actor_id": tenant.user.id,
        "facility_id": tenant.facility.id,
        "capability": "patient.view",
        "action": "GET",
        "blocker_type": "PERMISSION",
        "opaque_ref": "opaque-probe-1",
        "request_fingerprint": "e" * 64,
    }
    first = write_denial_audit(**kwargs)
    replay = write_denial_audit(**kwargs)
    assert first.pk == replay.pk
    assert first.denial_event_code == "AUTHORIZATION_DENIED"
    with pytest.raises(DenialAuditConflict):
        write_denial_audit(**{**kwargs, "request_fingerprint": "f" * 64})


def test_workflow_policy_is_typed_and_uses_frozen_defaults(tenant):
    policy = FacilityWorkflowPolicy.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        updated_by=tenant.user,
    )
    assert policy.queue_call_expiry_minutes == 10
    assert policy.queue_no_show_final_attempts == 3
    assert policy.public_board_identity_mode is None
    assert policy.triage_complaint_options == []
    assert policy.discount_approval_threshold is None
    assert policy.blind_stock_count is True
    assert policy.lab_allow_self_verification is False
    policy.triage_complaint_options = {"not": "a-list"}
    with pytest.raises(ValidationError):
        policy.full_clean()


def test_trace_validator_fails_without_mutating_canonical_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tools.validate_s00 import Validator

    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    shutil.copy2(root / "PROJECT_SPEC.md", fixture_root / "PROJECT_SPEC.md")
    shutil.copy2(root / "IMPLEMENTATION_BLUEPRINT.md", fixture_root / "IMPLEMENTATION_BLUEPRINT.md")
    (fixture_root / "blueprint-validation").mkdir()
    shutil.copy2(
        root / "blueprint-validation/TRACEABILITY.csv",
        fixture_root / "blueprint-validation/TRACEABILITY.csv",
    )
    shutil.copy2(
        root / "blueprint-validation/TRACEABILITY.md",
        fixture_root / "blueprint-validation/TRACEABILITY.md",
    )
    trace = fixture_root / "blueprint-validation/TRACEABILITY.csv"
    trace.write_bytes(trace.read_bytes() + b"\n")
    assert Validator(fixture_root).run() == 1
