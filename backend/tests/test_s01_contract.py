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

    check_in = schema["paths"]["/api/v1/reception/visits/check-in/"]["post"]
    check_in_response_ref = check_in["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    check_in_response = schema["components"]["schemas"][check_in_response_ref.rsplit("/", 1)[-1]]
    payer_binding = check_in_response["properties"]["payer_binding"]
    assert payer_binding["properties"]["id"] == {"type": "string", "format": "uuid"}
    assert payer_binding["properties"]["payer_type"]["enum"] == ["CASH", "SELF_PAY_MOMO"]
    assert payer_binding["properties"]["price_list_id"]["nullable"] is True

    summary = schema["paths"]["/api/v1/reception/patients/{id}/check-in-summary/"]["get"]
    summary_ref = summary["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    summary_response = schema["components"]["schemas"][summary_ref.rsplit("/", 1)[-1]]
    patient_fields = summary_response["properties"]["patient"]["properties"]
    assert set(patient_fields) == {"id", "patient_no", "display_name", "sex", "date_of_birth", "version"}
    assert "phone" not in patient_fields
    assert "address" not in patient_fields
