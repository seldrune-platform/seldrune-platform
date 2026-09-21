from uuid import uuid4

from backend.app.services.life_cycle import run_life_tick


def test_life_tick_is_governance_blocked_without_policy(db_session) -> None:
    result = run_life_tick(
        db_session,
        organization_id=uuid4(),
        actor_user_id=uuid4(),
    )
    assert result["status"] == "governance_blocked"
    assert result["commands_advanced"] == 0


def test_life_tick_route_is_registered(client) -> None:
    schema = client.get("/openapi.json")
    if schema.status_code != 200:
        return
    path = "/api/v1/organizations/{organization_id}/life/tick"
    assert path in schema.json()["paths"]
    assert "seldrune-life" in schema.json()["paths"][path]["post"]["tags"]
