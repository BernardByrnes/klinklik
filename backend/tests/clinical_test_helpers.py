def note_headers(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200
    assert response.data["consultation_etag"]
    return {"HTTP_IF_MATCH": response.data["consultation_etag"]}


def establish_synthetic_nka_review(client, encounter_id):
    encounter = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert encounter.status_code == 200, encounter.data
    status = client.post(
        f"/api/v1/clinic/patients/{encounter.data['patient']}/allergy-status/",
        {"status": "NKA"},
        HTTP_IF_MATCH=encounter.data["allergy_state_etag"],
        format="json",
    )
    assert status.status_code == 200, status.data
    review = client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/allergies/review/",
        {},
        HTTP_IF_MATCH=status.data["allergy_state_etag"],
        format="json",
    )
    assert review.status_code == 200, review.data
    assert review.data["allergies_review_is_current"] is True
    return review.data


def establish_synthetic_final_diagnosis(client, encounter_id):
    encounter = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert encounter.status_code == 200, encounter.data
    diagnosis = client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/diagnoses/",
        {
            "diagnosis_type": "FINAL",
            "code": "PHASE1-SYNTHETIC",
            "label": "Phase 1 synthetic development final diagnosis",
            "certainty_note": "Phase 1 synthetic development fixture",
            "is_primary": True,
        },
        HTTP_IF_MATCH=encounter.data["consultation_etag"],
        format="json",
    )
    assert diagnosis.status_code == 201, diagnosis.data
    return diagnosis.data
