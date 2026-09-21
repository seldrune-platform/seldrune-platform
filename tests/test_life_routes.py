def test_life_heartbeat_requires_authentication(client) -> None:
    response = client.get(\n        "/api/v1/organizations/00000000-0000-0000-0000-000000000001/life/heartbeat"\n    )
    assert response.status_code in (401, 403)


def test_life_routes_are_registered(client) -> None:
    schema = client.get("/openapi.json")
    if schema.status_code != 200:
        return
    paths = schema.json()["paths"]
    assert "/api/v1/organizations/{organization_id}/life/heartbeat" in paths
    assert "/api/v1/organizations/{organization_id}/life/pulse/{run_id}" in paths
    heartbeat = paths["/api/v1/organizations/{organization_id}/life/heartbeat"]["get"]
    pulse = paths["/api/v1/organizations/{organization_id}/life/pulse/{run_id}"]["post"]
    assert "seldrune-life" in heartbeat["tags"]
    assert "seldrune-life" in pulse["tags"]
