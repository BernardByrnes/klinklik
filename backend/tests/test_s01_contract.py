from pathlib import Path

from tools.generate_api_client import schema_for


def test_s01_openapi_keeps_status_specific_registration_and_typed_checkin_contracts():
    schema = schema_for(Path(__file__).resolve().parents[2])

    registration = schema["paths"]["/api/v1/reception/patients/register/"]["post"]
    responses = registration["responses"]
    assert set(responses) >= {"200", "201"}
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PatientDuplicateResponse"
    )
    assert responses["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PatientRegisterResponse"
    )
    assert "PatientDuplicateResponse" in schema["components"]["schemas"]
    duplicate_schema = schema["components"]["schemas"]["PatientDuplicateResponse"]
    assert set(duplicate_schema["required"]) == {"duplicate_candidates", "next_action"}
    duplicate_candidate = schema["components"]["schemas"]["PatientDuplicateResponse"]["properties"]["duplicate_candidates"]
    assert duplicate_candidate["type"] == "array"
    assert set(duplicate_candidate["items"]["properties"]) == {
        "id",
        "patient_no",
        "display_name",
        "match_score",
        "last_visit_date",
        "last_seen_at",
    }
    created_schema = schema["components"]["schemas"]["PatientRegisterResponse"]
    assert created_schema != duplicate_schema
    assert set(created_schema["required"]) == {"patient_id", "next_action"}
    assert set(created_schema["properties"]) == {"patient_id", "next_action"}
    assert created_schema["properties"]["next_action"]["enum"] == ["CHECK_IN"]
    assert duplicate_schema["properties"]["next_action"]["enum"] == ["RESOLVE_DUPLICATE"]

    check_in = schema["paths"]["/api/v1/reception/visits/check-in/"]["post"]
    check_in_response_ref = check_in["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    check_in_response = schema["components"]["schemas"][check_in_response_ref.rsplit("/", 1)[-1]]
    assert set(check_in_response["properties"]) == {
        "visit_id",
        "queue_id",
        "invoice_id",
        "patient_id",
        "next_action",
    }
    assert set(check_in_response["required"]) == set(check_in_response["properties"])

    summary = schema["paths"]["/api/v1/reception/patients/{id}/check-in-summary/"]["get"]
    summary_ref = summary["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    summary_response = schema["components"]["schemas"][summary_ref.rsplit("/", 1)[-1]]
    patient_fields = summary_response["properties"]["patient"]["properties"]
    assert set(patient_fields) == {"id", "patient_no", "display_name", "sex", "date_of_birth", "version"}
    assert "phone" not in patient_fields
    assert "address" not in patient_fields
