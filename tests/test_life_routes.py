def test_life_heartbeat_requires_authentication(client) -> None:
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/api/v1/organizations/{organization_id}/life/heartbeat")
    assert response.status_code in (401, 403)


def test_life_routes_are_registered(client) -> None:
    schema = client.get("/openapi.json")
    if schema.status_code != 200:
        return
    paths = schema.json()["paths"]
    heartbeat_path = "/api/v1/organizations/{organization_id}/life/heartbeat"
    pulse_path = "/api/v1/organizations/{organization_id}/life/pulse/{run_id}"
    assert heartbeat_path in paths
    assert pulse_path in paths
    heartbeat = paths[heartbeat_path]["get"]
    pulse = paths[pulse_path]["post"]
    assert "seldrune-life" in heartbeat["tags"]
    assert "seldrune-life" in pulse["tags"]
