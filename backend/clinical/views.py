from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from clinical.allergies import (
    AllergyDomainError,
    AllergyStateConflict,
    add_allergy,
    enter_allergy_in_error,
    review_encounter_allergies,
    set_allergy_status,
)
from clinical.concurrency import (
    ClinicalNoteRevisionConflict,
    consultation_note_etag,
    consultation_note_for_encounter,
    follow_up_recommendation_for_encounter,
)
from clinical.diagnoses import DiagnosisDomainError, DiagnosisRevisionConflict, create_diagnosis, remove_diagnosis, update_diagnosis
from clinical.diagnosis_state import active_diagnosis_snapshot
from clinical.dispositions import DispositionDomainError, DispositionRevisionConflict, set_disposition
from clinical.followups import FollowUpDomainError, FollowUpRevisionConflict, save_follow_up
from clinical.models import Allergy, Diagnosis, Encounter, TriageAssessment, TriageRecord
from application.clinical.commands import (
    encounter_open,
    encounter_sign,
    triage_complete,
    triage_record_complete,
    triage_record_save,
    triage_record_start,
)
from clinical.permissions import TriageMethodCapability, TriageRecordScopePermission
from clinical.triage import snapshot as triage_snapshot
from core.errors import CanonicalError
from core.mig003 import target_reads_enabled_mig003, target_writes_enabled_mig003
from core.permissions import (
    HasCapability,
    IsTenantMember,
    QueueScopePermission,
    coerce_queue_identifier,
    queue_scope_pairs,
    scope_allows,
)
from patients.models import Patient
from clinical.serializers import (
    AllergyCreateSerializer,
    DiagnosisSerializer,
    DiagnosisWriteSerializer,
    DispositionWriteSerializer,
    FollowUpRecommendationSerializer,
    FollowUpWriteSerializer,
    AllergyEnteredInErrorSerializer,
    AllergyStatusWriteSerializer,
    EncounterSerializer,
    EncounterCreateSerializer,
    TriageResponseSerializer,
    TriageRecordCompleteResponseSerializer,
    TriageRecordCompleteSerializer,
    TriageRecordSaveSerializer,
    TriageRecordSaveResponseSerializer,
    TriageRecordStartResponseSerializer,
    TriageRecordStartSerializer,
    AllergyStateResponseSerializer,
    DiagnosisStateResponseSerializer,
    DispositionResponseSerializer,
    FollowUpStateResponseSerializer,
    NoteResponseSerializer,
    NoteAmendSerializer,
    NoteWriteSerializer,
    TriageSerializer,
)
from clinical.services import (
    PresentingComplaintRequired,
    amend_note,
    save_note,
)
from core.tenant_api import TenantAPIView
from core.errors import CanonicalError
from core.idempotency import json_safe
from scheduling.models import QueueEntry
from scheduling.serializers import QueueEntrySerializer


def _mig002_command_mode(organisation):
    from core.models import MigrationCutover

    return MigrationCutover.objects.filter(
        organisation=organisation,
        migration_id="MIG-002",
        phase__in={"CONSTRAINED", "CUTOVER"},
        target_writes_enabled=True,
    ).exists()


def _require_canonical_queue_version(request, expected_version):
    """Canonical stage commands need the current queue version.

    The legacy compatibility path keeps accepting a version-less request; the
    canonical writer must not start service from an unconfirmed row.
    """

    if expected_version is not None:
        return
    if not _mig002_command_mode(request.organisation):
        return
    raise CanonicalError(
        "PRECONDITION_REQUIRED",
        "A current queue version is required in expected_version or If-Match.",
        status_code=428,
    )


class TriageView(TenantAPIView):
    capability = "triage.record"
    # The canonical stage command must be scoped to the row's own department
    # and work type, before idempotency replay can expose a stored result.
    permission_classes = [IsAuthenticated, IsTenantMember, HasCapability, QueueScopePermission]
    idempotency_operation = "CMD-027"
    requires_idempotency = True
    serializer_class = TriageSerializer
    response_serializer_class = TriageResponseSerializer

    def requires_idempotency_for_request(self, request):
        return _mig002_command_mode(request.organisation)

    def replay_idempotent_response(self, record):
        reference = record.result_reference or {}
        assessment_id = reference.get("entity_id") if isinstance(reference, dict) else None
        assessment = TriageAssessment.objects.filter(
            id=assessment_id,
            organisation=self.request.organisation,
            facility=self.request.facility,
        ).first()
        if assessment is None:
            return record.response_body
        queue_entry = QueueEntry.objects.select_related("patient", "department").filter(
            id=assessment.queue_entry_id,
            organisation=self.request.organisation,
            facility=self.request.facility,
        ).first()
        if queue_entry is None:
            return record.response_body
        return self._response_body(assessment, queue_entry)

    @staticmethod
    def _response_body(assessment, queue_entry):
        return json_safe({
            "id": assessment.id,
            "queue_entry": QueueEntrySerializer(queue_entry).data,
            "acuity": assessment.acuity,
            "chief_complaint": assessment.chief_complaint,
            "observations": assessment.observations,
        })

    def post(self, request, queue_id):
        serializer = TriageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _clinical_expected_version(request, values)
        _require_canonical_queue_version(request, expected_version)
        values.pop("expected_version", None)
        try:
            outcome = triage_complete(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                queue_entry_id=queue_id,
                data=values,
                expected_version=expected_version,
            )
        except CanonicalError:
            raise
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        assessment = outcome.assessment
        body = self._response_body(assessment, outcome.source)
        response = Response(body, status=status.HTTP_201_CREATED)
        response.idempotency_body = {
            "id": str(assessment.id),
            "queue_entry_id": str(outcome.source.id),
            "state": outcome.source.state,
        }
        response.result_reference = {
            "entity_type": "TriageAssessment",
            "entity_id": str(assessment.id),
        }
        return response


def _clinical_expected_version(request, values):
    body_version = values.get("expected_version")
    header = request.headers.get("If-Match")
    if not header:
        return body_version
    value = str(header).strip()
    if value.startswith("W/"):
        raise CanonicalError("INVALID_IF_MATCH", "If-Match must be a strong queue version.", status_code=400)
    try:
        header_version = int(value.strip('"'))
    except (TypeError, ValueError) as exc:
        raise CanonicalError("INVALID_IF_MATCH", "If-Match must contain the queue version.", status_code=400) from exc
    if header_version < 1:
        raise CanonicalError("INVALID_IF_MATCH", "If-Match must contain a positive queue version.", status_code=400)
    if body_version is not None and int(body_version) != header_version:
        raise CanonicalError("VERSION_CONFLICT", "The body version and If-Match value do not agree.", status_code=412)
    return header_version


def _required_if_match(request, detail="If-Match is required for clinical note mutations."):
    expected_etag = request.headers.get("If-Match")
    if not expected_etag:
        return None, Response(
            {
                "code": "PRECONDITION_REQUIRED",
                "detail": detail,
            },
            status=status.HTTP_428_PRECONDITION_REQUIRED,
        )
    return expected_etag, None


def _revision_conflict_response(exc, http_status=status.HTTP_409_CONFLICT):
    response = Response(
        {
            "code": "CLINICAL_NOTE_REVISION_CONFLICT",
            "detail": "This consultation changed elsewhere; review the current record before retrying.",
            "etag": exc.current_etag,
            "consultation_etag": exc.current_etag,
            "status": exc.current_status,
            "encounter_status": exc.current_encounter_status,
            "content": exc.current_content,
            "complaints": exc.current_complaints,
            "diagnoses": exc.current_diagnoses,
            "disposition": exc.current_disposition,
            "disposition_note": exc.current_disposition_note,
            "follow_up": exc.current_follow_up,
            "saved_at": exc.current_saved_at,
        },
        status=http_status,
    )
    response["ETag"] = exc.current_etag
    return response


def _diagnosis_conflict_response(exc):
    response = Response(
        {
            "code": "DIAGNOSIS_REVISION_CONFLICT",
            "detail": "This consultation changed elsewhere; review the current diagnoses before retrying.",
            "etag": exc.current_etag,
            "consultation_etag": exc.current_etag,
            "encounter_status": exc.current_encounter_status,
            "diagnoses": exc.current_diagnoses,
        },
        status=status.HTTP_412_PRECONDITION_FAILED,
    )
    response["ETag"] = exc.current_etag
    return response


def _disposition_conflict_response(exc):
    response = Response(
        {
            "code": "DISPOSITION_REVISION_CONFLICT",
            "detail": "This consultation changed elsewhere; review the current disposition before retrying.",
            "etag": exc.current_etag,
            "consultation_etag": exc.current_etag,
            "status": exc.current_status,
            "encounter_status": exc.current_encounter_status,
            "content": exc.current_content,
            "complaints": exc.current_complaints,
            "diagnoses": exc.current_diagnoses,
            "disposition": exc.current_disposition,
            "disposition_note": exc.current_disposition_note,
            "follow_up": exc.current_follow_up,
            "saved_at": exc.current_saved_at,
        },
        status=status.HTTP_412_PRECONDITION_FAILED,
    )
    response["ETag"] = exc.current_etag
    return response


def _diagnosis_state_response(*, encounter, note, diagnoses, status_code=status.HTTP_200_OK):
    etag = consultation_note_etag(encounter=encounter, note=note)
    response = Response(
        {
            "diagnoses": diagnoses,
            "consultation_etag": etag,
        },
        status=status_code,
    )
    response["ETag"] = etag
    return response


def _disposition_response(*, encounter, note, status_code=status.HTTP_200_OK):
    encounter.refresh_from_db(fields=["disposition", "disposition_note", "status", "updated_at"])
    if note is not None:
        note.refresh_from_db(fields=["content", "status", "updated_at"])
    etag = consultation_note_etag(encounter=encounter, note=note)
    data = {
        "disposition": encounter.disposition,
        "disposition_note": encounter.disposition_note,
        "consultation_etag": etag,
        "encounter_status": encounter.status,
    }
    response = Response(data, status=status_code)
    response["ETag"] = etag
    return response


def _note_response(*, encounter, note, include_version=False):
    encounter.refresh_from_db(fields=["complaints", "status", "signed_at", "updated_at"])
    note.refresh_from_db(fields=["updated_at"])
    data = {
        "note": note.id,
        "status": note.status,
        "content": note.content,
        "complaints": list(encounter.complaints or []),
        "etag": consultation_note_etag(encounter=encounter, note=note),
        "saved_at": note.updated_at.isoformat(),
    }
    if include_version:
        data["current_version"] = note.current_version
    response = Response(data)
    response["ETag"] = data["etag"]
    return response


def _allergy_conflict_response(exc):
    snapshot = exc.snapshot
    response = Response(
        {
            "code": exc.code,
            "detail": exc.detail,
            "allergy_status": snapshot["status"],
            "active_allergies": snapshot["active_allergies"],
            "allergy_revision": snapshot["revision"],
            "allergy_state_etag": snapshot["etag"],
        },
        status=status.HTTP_412_PRECONDITION_FAILED,
    )
    response["ETag"] = snapshot["etag"]
    return response


def _allergy_state_response(*, snapshot, status_code=status.HTTP_200_OK, patient=None, allergy=None):
    data = {
        "allergy_status": snapshot["status"],
        "active_allergies": snapshot["active_allergies"],
        "allergy_revision": snapshot["revision"],
        "allergy_state_etag": snapshot["etag"],
    }
    if patient is not None:
        data["patient"] = str(patient.id)
    if allergy is not None:
        data["allergy"] = {
            **{
                "id": str(allergy.id),
                "substance": allergy.substance,
                "reaction": allergy.reaction,
                "severity": allergy.severity,
            },
            "status": allergy.status,
            "recorded_at": allergy.recorded_at.isoformat() if allergy.recorded_at else None,
        }
    response = Response(data, status=status_code)
    response["ETag"] = snapshot["etag"]
    return response


class PatientAllergyView(TenantAPIView):
    capability = "allergy.manage"
    idempotency_operation = "CMD-092"
    requires_idempotency = True
    serializer_class = AllergyCreateSerializer
    response_serializer_class = AllergyStateResponseSerializer

    def post(self, request, patient_id):
        patient = get_object_or_404(Patient, id=patient_id, organisation=request.organisation)
        serializer = AllergyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            allergy, snapshot = add_allergy(
                organisation=request.organisation,
                facility=request.facility,
                patient=patient,
                actor=request.user,
                request=request,
                **serializer.validated_data,
            )
        except AllergyStateConflict as exc:
            return _allergy_conflict_response(exc)
        except AllergyDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _allergy_state_response(
            snapshot=snapshot,
            status_code=status.HTTP_201_CREATED,
            patient=patient,
            allergy=allergy,
        )


class PatientAllergyStatusView(TenantAPIView):
    capability = "allergy.manage"
    idempotency_operation = "CMD-093"
    requires_idempotency = True
    serializer_class = AllergyStatusWriteSerializer
    response_serializer_class = AllergyStateResponseSerializer

    def post(self, request, patient_id):
        patient = get_object_or_404(Patient, id=patient_id, organisation=request.organisation)
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for patient allergy status mutations.",
        )
        if error_response is not None:
            return error_response
        serializer = AllergyStatusWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            _, snapshot = set_allergy_status(
                organisation=request.organisation,
                facility=request.facility,
                patient=patient,
                actor=request.user,
                expected_etag=expected_etag,
                request=request,
                **serializer.validated_data,
            )
        except AllergyStateConflict as exc:
            return _allergy_conflict_response(exc)
        except AllergyDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _allergy_state_response(snapshot=snapshot, patient=patient)


class PatientAllergyEnteredInErrorView(TenantAPIView):
    capability = "allergy.manage"
    idempotency_operation = "CMD-094"
    requires_idempotency = True
    serializer_class = AllergyEnteredInErrorSerializer
    response_serializer_class = AllergyStateResponseSerializer

    def post(self, request, patient_id, allergy_id):
        patient = get_object_or_404(Patient, id=patient_id, organisation=request.organisation)
        allergy = get_object_or_404(
            Allergy,
            id=allergy_id,
            organisation=request.organisation,
            facility=request.facility,
            patient=patient,
        )
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for entering an allergy in error.",
        )
        if error_response is not None:
            return error_response
        serializer = AllergyEnteredInErrorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entered, _, snapshot = enter_allergy_in_error(
                organisation=request.organisation,
                facility=request.facility,
                patient=patient,
                allergy=allergy,
                actor=request.user,
                expected_etag=expected_etag,
                request=request,
                **serializer.validated_data,
            )
        except AllergyStateConflict as exc:
            return _allergy_conflict_response(exc)
        except AllergyDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _allergy_state_response(
            snapshot=snapshot,
            patient=patient,
            allergy=entered,
        )


class EncounterAllergyReviewView(TenantAPIView):
    capability = "clinical.note.sign"
    idempotency_operation = "CMD-095"
    requires_idempotency = True
    response_serializer_class = AllergyStateResponseSerializer

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter,
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for allergy review acknowledgement.",
        )
        if error_response is not None:
            return error_response
        try:
            reviewed, snapshot = review_encounter_allergies(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                expected_etag=expected_etag,
                request=request,
            )
        except AllergyStateConflict as exc:
            return _allergy_conflict_response(exc)
        except AllergyDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        response = Response(
            {
                "encounter": str(reviewed.id),
                "allergy_status": snapshot["status"],
                "active_allergies": snapshot["active_allergies"],
                "allergy_revision": snapshot["revision"],
                "allergy_state_etag": snapshot["etag"],
                "allergies_reviewed_at": reviewed.allergies_reviewed_at.isoformat(),
                "allergies_reviewed_revision": reviewed.allergies_reviewed_revision,
                "allergies_review_is_current": True,
            }
        )
        response["ETag"] = snapshot["etag"]
        return response


class EncounterListCreateView(TenantAPIView):
    capability = "clinical.note.create"
    permission_classes = [IsAuthenticated, IsTenantMember, HasCapability, QueueScopePermission]
    idempotency_operation = "CMD-030"
    requires_idempotency = True
    serializer_class = EncounterCreateSerializer
    response_serializer_class = EncounterSerializer

    def requires_idempotency_for_request(self, request):
        return _mig002_command_mode(request.organisation)

    def replay_idempotent_response(self, record):
        reference = record.result_reference or {}
        encounter_id = reference.get("entity_id") if isinstance(reference, dict) else None
        encounter = Encounter.objects.select_related("patient", "visit", "queue_entry").filter(
            id=encounter_id,
            organisation=self.request.organisation,
            facility=self.request.facility,
        ).first()
        if encounter is None:
            return record.response_body
        return json_safe(EncounterSerializer(encounter).data)

    def post(self, request):
        serializer = EncounterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        queue_entry_id = values["queue_entry_id"]
        if not queue_entry_id:
            return Response({"detail": "queue_entry_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        expected_version = _clinical_expected_version(request, values)
        _require_canonical_queue_version(request, expected_version)
        try:
            outcome = encounter_open(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                queue_entry_id=queue_entry_id,
                expected_version=expected_version,
            )
            encounter = outcome.encounter
        except CanonicalError:
            raise
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = json_safe(EncounterSerializer(encounter).data)
        response = Response(data, status=status.HTTP_201_CREATED)
        response["ETag"] = data["consultation_etag"]
        response.idempotency_body = {"id": str(encounter.id)}
        response.result_reference = {
            "entity_type": "Encounter",
            "entity_id": str(encounter.id),
        }
        return response


class EncounterDiagnosisListCreateView(TenantAPIView):
    capability = "clinical.note.create"
    idempotency_operation = "CMD-096"
    requires_idempotency = True
    serializer_class = DiagnosisWriteSerializer
    response_serializer_class = DiagnosisStateResponseSerializer
    response_is_list = False

    def _encounter(self, request, pk):
        return get_object_or_404(
            Encounter,
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )

    def get(self, request, pk):
        encounter = self._encounter(request, pk)
        note = consultation_note_for_encounter(encounter)
        return _diagnosis_state_response(
            encounter=encounter,
            note=note,
            diagnoses=active_diagnosis_snapshot(encounter),
        )

    def post(self, request, pk):
        encounter = self._encounter(request, pk)
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for diagnosis mutations.",
        )
        if error_response is not None:
            return error_response
        serializer = DiagnosisWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_diagnosis(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                data=serializer.validated_data,
                expected_etag=expected_etag,
                request=request,
            )
        except DiagnosisRevisionConflict as exc:
            return _diagnosis_conflict_response(exc)
        except DiagnosisDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _diagnosis_state_response(
            encounter=result["encounter"],
            note=result["note"],
            diagnoses=result["diagnoses"],
            status_code=status.HTTP_201_CREATED,
        )


class EncounterDiagnosisDetailView(TenantAPIView):
    # Registry CMD-097 (diagnosis_remove) is a RETIRED tombstone. This route
    # supports draft diagnosis amendment/removal only; no active CMD exists to
    # label, so it is intentionally left outside idempotency enforcement.
    capability = "clinical.note.create"
    serializer_class = DiagnosisWriteSerializer
    response_serializer_class = DiagnosisStateResponseSerializer

    def _encounter(self, request, pk):
        return get_object_or_404(
            Encounter,
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )

    def _diagnosis(self, request, encounter, diagnosis_id):
        return get_object_or_404(
            Diagnosis,
            id=diagnosis_id,
            encounter=encounter,
            organisation=request.organisation,
            facility=request.facility,
            status="ACTIVE",
        )

    def patch(self, request, pk, diagnosis_id):
        encounter = self._encounter(request, pk)
        self._diagnosis(request, encounter, diagnosis_id)
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for diagnosis mutations.",
        )
        if error_response is not None:
            return error_response
        serializer = DiagnosisWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            result = update_diagnosis(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                diagnosis_id=diagnosis_id,
                data=serializer.validated_data,
                expected_etag=expected_etag,
                request=request,
            )
        except DiagnosisRevisionConflict as exc:
            return _diagnosis_conflict_response(exc)
        except DiagnosisDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _diagnosis_state_response(
            encounter=result["encounter"],
            note=result["note"],
            diagnoses=result["diagnoses"],
        )


class EncounterDiagnosisRemoveView(TenantAPIView):
    # See EncounterDiagnosisDetailView: the registry's remove command is retired.
    # No active idempotency namespace is invented for this retained draft route.
    capability = "clinical.note.create"
    response_serializer_class = DiagnosisStateResponseSerializer

    def post(self, request, pk, diagnosis_id):
        encounter = get_object_or_404(
            Encounter,
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )
        get_object_or_404(
            Diagnosis,
            id=diagnosis_id,
            encounter=encounter,
            organisation=request.organisation,
            facility=request.facility,
            status="ACTIVE",
        )
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for diagnosis mutations.",
        )
        if error_response is not None:
            return error_response
        try:
            result = remove_diagnosis(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                diagnosis_id=diagnosis_id,
                expected_etag=expected_etag,
                request=request,
            )
        except DiagnosisRevisionConflict as exc:
            return _diagnosis_conflict_response(exc)
        except DiagnosisDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        return _diagnosis_state_response(
            encounter=result["encounter"],
            note=result["note"],
            diagnoses=result["diagnoses"],
        )


class EncounterDispositionView(TenantAPIView):
    capability = "clinical.note.create"
    idempotency_operation = "CMD-099"
    requires_idempotency = True
    serializer_class = DispositionWriteSerializer
    response_serializer_class = DispositionResponseSerializer

    def patch(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for disposition mutations.",
        )
        if error_response is not None:
            return error_response
        serializer = DispositionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = set_disposition(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                data=serializer.validated_data,
                expected_etag=expected_etag,
                request=request,
            )
        except DispositionRevisionConflict as exc:
            return _disposition_conflict_response(exc)
        except DispositionDomainError as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _disposition_response(encounter=result["encounter"], note=result["note"])


class EncounterFollowUpView(TenantAPIView):
    capability = "clinical.note.create"
    idempotency_operation = "CMD-101"
    requires_idempotency = True
    serializer_class = FollowUpWriteSerializer
    response_serializer_class = FollowUpStateResponseSerializer
    response_is_list = False

    def _encounter(self, request, pk):
        return get_object_or_404(
            Encounter,
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )

    def get(self, request, pk):
        encounter = self._encounter(request, pk)
        follow_up = follow_up_recommendation_for_encounter(encounter)
        note = consultation_note_for_encounter(encounter)
        etag = consultation_note_etag(encounter=encounter, note=note)
        data = {
            "follow_up": FollowUpRecommendationSerializer(follow_up).data if follow_up is not None else None,
            "consultation_etag": etag,
            "encounter_status": encounter.status,
        }
        response = Response(data)
        response["ETag"] = etag
        return response

    def patch(self, request, pk):
        encounter = self._encounter(request, pk)
        expected_etag, error_response = _required_if_match(
            request,
            detail="If-Match is required for follow-up mutations.",
        )
        if error_response is not None:
            return error_response
        serializer = FollowUpWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            result = save_follow_up(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                data=serializer.validated_data,
                expected_etag=expected_etag,
                request=request,
            )
        except FollowUpRevisionConflict as exc:
            response = Response(
                {
                    "code": "FOLLOW_UP_REVISION_CONFLICT",
                    "detail": "This consultation changed elsewhere; review the current follow-up before retrying.",
                    "etag": exc.current_etag,
                    "consultation_etag": exc.current_etag,
                    "status": exc.current_status,
                    "encounter_status": exc.current_encounter_status,
                    "content": exc.current_content,
                    "complaints": exc.current_complaints,
                    "diagnoses": exc.current_diagnoses,
                    "disposition": exc.current_disposition,
                    "disposition_note": exc.current_disposition_note,
                    "follow_up": exc.current_follow_up,
                    "saved_at": exc.current_saved_at,
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
            response["ETag"] = exc.current_etag
            return response
        except FollowUpDomainError as exc:
            return Response({"code": exc.code, "detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        saved = result["follow_up"]
        saved.refresh_from_db()
        etag = consultation_note_etag(encounter=result["encounter"], note=result["note"])
        data = {
            "follow_up": FollowUpRecommendationSerializer(saved).data,
            "consultation_etag": etag,
            "encounter_status": result["encounter"].status,
        }
        response = Response(data)
        response["ETag"] = etag
        return response

class EncounterDetailView(TenantAPIView):
    capability = "clinical.note.create"
    response_serializer_class = EncounterSerializer

    def get_object(self, request, pk):
        return get_object_or_404(
            Encounter.objects.prefetch_related("notes", "diagnoses", "follow_ups"),
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )

    def get(self, request, pk):
        data = EncounterSerializer(self.get_object(request, pk)).data
        response = Response(data)
        response["ETag"] = data["consultation_etag"]
        return response


class EncounterNoteView(TenantAPIView):
    capability = "clinical.note.create"
    idempotency_operation = "CMD-031"
    requires_idempotency = True
    serializer_class = NoteWriteSerializer
    response_serializer_class = NoteResponseSerializer

    def _save(self, request, pk, conflict_status):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = save_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                complaints=serializer.validated_data.get("complaints"),
                expected_etag=expected_etag,
                request=request,
            )
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc, http_status=conflict_status)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=note)

    def post(self, request, pk):
        return self._save(request, pk, conflict_status=status.HTTP_409_CONFLICT)

    def patch(self, request, pk):
        return self._save(request, pk, conflict_status=status.HTTP_412_PRECONDITION_FAILED)

class EncounterSignView(TenantAPIView):
    capability = "clinical.note.sign"
    idempotency_operation = "CMD-035"
    requires_idempotency = True
    operation_id = "signEncounter"
    serializer_class = NoteWriteSerializer
    response_serializer_class = NoteResponseSerializer

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            outcome = encounter_sign(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter_id=encounter.id,
                content=serializer.validated_data["content"],
                complaints=serializer.validated_data.get("complaints"),
                expected_etag=expected_etag,
                request=request,
            )
            encounter.refresh_from_db()
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc)
        except AllergyStateConflict as exc:
            return _allergy_conflict_response(exc)
        except AllergyDomainError as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DiagnosisDomainError as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DispositionDomainError as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PresentingComplaintRequired as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=outcome.note, include_version=True)


class EncounterAmendView(TenantAPIView):
    capability = "clinical.note.amend"
    idempotency_operation = "CMD-038"
    requires_idempotency = True
    serializer_class = NoteAmendSerializer
    response_serializer_class = NoteResponseSerializer

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteAmendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = amend_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                reason=serializer.validated_data["reason"],
                expected_etag=expected_etag,
                request=request,
            )
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=note, include_version=True)


def _mig003_triage_writes_required(organisation):
    if not target_writes_enabled_mig003(organisation):
        raise CanonicalError(
            "MIGRATION_TARGET_DISABLED",
            "Canonical triage is unavailable while migration compatibility is restored.",
            status_code=503,
            retryable=True,
        )


def _mig003_triage_reads_required(organisation):
    if not target_reads_enabled_mig003(organisation):
        raise CanonicalError(
            "MIGRATION_TARGET_DISABLED",
            "Canonical triage records are temporarily unavailable.",
            status_code=503,
            retryable=True,
        )


def _strong_if_match(request):
    header = request.headers.get("If-Match")
    if not header:
        return None
    value = str(header).strip()
    if value.startswith("W/"):
        raise CanonicalError(
            "INVALID_IF_MATCH", "If-Match must be a strong triage version.", status_code=400
        )
    value = value.strip('"')
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise CanonicalError(
            "INVALID_IF_MATCH", "If-Match must contain the triage version.", status_code=400
        ) from exc
    if version < 1:
        raise CanonicalError(
            "INVALID_IF_MATCH", "If-Match must contain a positive version.", status_code=400
        )
    return version


def _triage_expected_version(request, values, *, field="expected_version"):
    header = _strong_if_match(request)
    body = values.get(field)
    if header is not None and body is not None and int(body) != header:
        raise CanonicalError(
            "VERSION_CONFLICT",
            "The body version and If-Match value do not agree.",
            status_code=412,
        )
    resolved = header if header is not None else body
    if resolved is None:
        raise CanonicalError(
            "PRECONDITION_REQUIRED",
            "A current version is required in the body or If-Match.",
            status_code=428,
            metadata={"field": field},
        )
    return int(resolved)


def _triage_record_for_request(request, identifier):
    record_id = coerce_queue_identifier(identifier)
    if record_id is None:
        raise CanonicalError(
            "NOT_FOUND", "The triage record was not found in this facility.", status_code=404
        )
    record = TriageRecord.objects.filter(
        organisation_id=request.organisation.id,
        facility_id=request.facility.id,
        id=record_id,
    ).first()
    if record is None:
        raise CanonicalError(
            "NOT_FOUND", "The triage record was not found in this facility.", status_code=404
        )
    return record


def _triage_scope_allows(request, view, record):
    source = QueueEntry.objects.filter(
        organisation_id=request.organisation.id,
        facility_id=request.facility.id,
        visit_id=record.visit_id,
        queue_type="TRIAGE",
    ).values("department_id", "queue_type").first()
    if source is None:
        return False
    write = request.method in {"POST", "PUT", "PATCH"}
    attribute = "triage_write_capabilities" if write else "triage_read_capabilities"
    capabilities = tuple(
        getattr(view, attribute, ())
        or getattr(view, "triage_capabilities", ())
        or (getattr(view, "capability", None),)
    )
    pairs = queue_scope_pairs(
        organisation=request.organisation,
        facility=request.facility,
        user=request.user,
        capabilities=capabilities,
    )
    return scope_allows(pairs, source["department_id"], source["queue_type"])


def _triage_replay_denial():
    return CanonicalError(
        "NOT_FOUND", "The triage record was not found in this facility.", status_code=404
    )


def _triage_response(body, *, record, idempotency_body, status_code=200):
    data = json_safe(body)
    response = Response(data, status=status_code)
    response["ETag"] = f'"{record.row_version}"'
    response.idempotency_body = json_safe(idempotency_body)
    response.result_reference = {
        "entity_type": "TriageRecord",
        "entity_id": str(record.id),
    }
    return response


class TriageRecordStartView(TenantAPIView):
    """CMD-025: start/resume triage on one TRIAGE queue entry."""

    capability = "triage.create"
    triage_capabilities = ("triage.create",)
    permission_classes = [
        IsAuthenticated,
        IsTenantMember,
        HasCapability,
        QueueScopePermission,
    ]
    idempotency_operation = "CMD-025"
    requires_idempotency = True
    serializer_class = TriageRecordStartSerializer
    response_serializer_class = TriageRecordStartResponseSerializer

    def requires_idempotency_for_request(self, request):
        _mig003_triage_writes_required(request.organisation)
        return True

    def replay_idempotent_response(self, record):
        reference = record.result_reference if isinstance(record.result_reference, dict) else {}
        record_id = reference.get("entity_id")
        if record_id is None:
            return record.response_body
        target = _triage_record_for_request(self.request, record_id)
        if not _triage_scope_allows(self.request, self, target):
            raise _triage_replay_denial()
        queue = (
            QueueEntry.objects.filter(
                organisation_id=self.request.organisation.id,
                facility_id=self.request.facility.id,
                visit_id=target.visit_id,
                queue_type="TRIAGE",
            )
            .order_by("queue_time", "id")
            .first()
        )
        if queue is None:
            raise _triage_replay_denial()
        return json_safe(
            {
                "triage_record": triage_snapshot(target),
                "queue_entry": QueueEntrySerializer(queue).data,
            }
        )

    def post(self, request, queue_id):
        serializer = TriageRecordStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        queue_version = _triage_expected_version(request, values)
        outcome = triage_record_start(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=queue_id,
            expected_queue_version=queue_version,
        )
        body = {
            "triage_record": triage_snapshot(outcome.record),
            "queue_entry": QueueEntrySerializer(outcome.queue).data,
        }
        return _triage_response(
            body,
            record=outcome.record,
            idempotency_body={
                "triage_record_id": str(outcome.record.id),
                "record_version": outcome.record.row_version,
                "queue_entry_id": str(outcome.queue.id),
                "queue_version": outcome.queue.version,
            },
        )


class TriageRecordDetailView(TenantAPIView):
    """GET/PATCH the scoped draft or completed triage snapshot."""

    triage_read_capability = "triage.read"
    triage_write_capability = "triage.create"
    triage_read_capabilities = ("triage.read",)
    triage_write_capabilities = ("triage.create",)
    permission_classes = [
        IsAuthenticated,
        IsTenantMember,
        TriageMethodCapability,
        TriageRecordScopePermission,
    ]
    idempotency_operation = "CMD-026"
    requires_idempotency = True
    serializer_class = TriageRecordSaveSerializer
    response_serializer_class = TriageRecordSaveResponseSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if (
            request.method == "GET"
            and response.status_code == 200
            and getattr(self, "_record_etag", None) is not None
        ):
            response["ETag"] = f'"{self._record_etag}"'
        return response

    def get(self, request, pk):
        _mig003_triage_reads_required(request.organisation)
        record = _triage_record_for_request(request, pk)
        self._record_etag = record.row_version
        return Response(json_safe({"triage_record": triage_snapshot(record)}))

    def requires_idempotency_for_request(self, request):
        _mig003_triage_writes_required(request.organisation)
        return True

    def replay_idempotent_response(self, record):
        reference = record.result_reference if isinstance(record.result_reference, dict) else {}
        record_id = reference.get("entity_id")
        if record_id is None:
            return record.response_body
        target = _triage_record_for_request(self.request, record_id)
        if not _triage_scope_allows(self.request, self, target):
            raise _triage_replay_denial()
        return json_safe({"triage_record": triage_snapshot(target)})

    def patch(self, request, pk):
        _mig003_triage_writes_required(request.organisation)
        serializer = TriageRecordSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected = _triage_expected_version(request, values)
        record = triage_record_save(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            triage_record_id=pk,
            payload=values,
            expected_version=expected,
        )
        body = {"triage_record": triage_snapshot(record)}
        return _triage_response(
            body,
            record=record,
            idempotency_body={
                "triage_record_id": str(record.id),
                "record_version": record.row_version,
            },
        )


class TriageRecordCompleteView(TenantAPIView):
    """CMD-027: complete the draft and create the consultation destination."""

    capability = "triage.create"
    triage_write_capabilities = ("triage.create",)
    permission_classes = [
        IsAuthenticated,
        IsTenantMember,
        HasCapability,
        TriageRecordScopePermission,
    ]
    idempotency_operation = "CMD-027"
    requires_idempotency = True
    serializer_class = TriageRecordCompleteSerializer
    response_serializer_class = TriageRecordCompleteResponseSerializer

    def requires_idempotency_for_request(self, request):
        _mig003_triage_writes_required(request.organisation)
        return True

    def replay_idempotent_response(self, record):
        reference = record.result_reference if isinstance(record.result_reference, dict) else {}
        record_id = reference.get("entity_id")
        if record_id is None:
            return record.response_body
        target = _triage_record_for_request(self.request, record_id)
        if not _triage_scope_allows(self.request, self, target):
            raise _triage_replay_denial()
        stored = record.response_body if isinstance(record.response_body, dict) else {}
        source = (
            QueueEntry.objects.filter(
                organisation_id=self.request.organisation.id,
                facility_id=self.request.facility.id,
                id=stored.get("source_queue_entry_id"),
            ).first()
            if stored.get("source_queue_entry_id")
            else None
        )
        destination = (
            QueueEntry.objects.filter(
                organisation_id=self.request.organisation.id,
                facility_id=self.request.facility.id,
                id=stored.get("destination_queue_entry_id"),
            ).first()
            if stored.get("destination_queue_entry_id")
            else None
        )
        if source is None or destination is None:
            raise _triage_replay_denial()
        return json_safe(
            {
                "triage_record": triage_snapshot(target),
                "source_queue_entry_id": str(source.id),
                "source_state": source.state,
                "destination_queue_entry_id": str(destination.id),
                "destination_state": destination.state,
            }
        )

    def post(self, request, pk):
        serializer = TriageRecordCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected = _triage_expected_version(request, values)
        queue_version = values.get("expected_queue_version")
        if queue_version is None:
            raise CanonicalError(
                "PRECONDITION_REQUIRED",
                "A current queue version is required in expected_queue_version.",
                status_code=428,
                metadata={"field": "expected_queue_version"},
            )
        outcome = triage_record_complete(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            triage_record_id=pk,
            payload=values,
            expected_version=expected,
            expected_queue_version=queue_version,
        )
        body = {
            "triage_record": triage_snapshot(outcome.record),
            "source_queue_entry_id": str(outcome.source.id),
            "source_state": outcome.source.state,
            "destination_queue_entry_id": str(outcome.destination.id),
            "destination_state": outcome.destination.state,
        }
        return _triage_response(
            body,
            record=outcome.record,
            idempotency_body={
                "triage_record_id": str(outcome.record.id),
                "record_version": outcome.record.row_version,
                "source_queue_entry_id": str(outcome.source.id),
                "destination_queue_entry_id": str(outcome.destination.id),
            },
        )
