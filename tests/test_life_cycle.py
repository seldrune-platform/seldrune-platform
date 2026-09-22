def test_life_tick_requires_authentication(client) -> None:
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(f"/api/v1/organizations/{organization_id}/life/tick")
    assert response.status_code in (401, 403)


def test_life_tick_route_is_registered(client) -> None:
    schema = client.get("/openapi.json")
    if schema.status_code != 200:
        return
    path = "/api/v1/organizations/{organization_id}/life/tick"
    assert path in schema.json()["paths"]
    assert "seldrune-life" in schema.json()["paths"][path]["post"]["tags"]
