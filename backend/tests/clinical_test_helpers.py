def note_headers(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200
    assert response.data["consultation_etag"]
    return {"HTTP_IF_MATCH": response.data["consultation_etag"]}
