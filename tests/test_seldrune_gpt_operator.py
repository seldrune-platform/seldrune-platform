from tests.test_autonomous_execution import client as _client  # noqa: F401
from tests.test_autonomous_execution import register_owner


def test_operator_risk_classification_is_explicit():
    from backend.app.api.routes.seldrune_gpt import _operator_risk_reasons

    assert _operator_risk_reasons("Analyze the organization") == []
    reasons = _operator_risk_reasons(
        "Deploy to production, send an email, and pay the invoice"
    )
    assert "production_change" in reasons
    assert "external_communication" in reasons
    assert "financial_commitment" in reasons


def test_gpt_operator_requires_auth(client):
    organization_id = "00000000-0000-0000-0000-000000000001"
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        json={"order": "Analyze the organization status"},
    )
    assert response.status_code in {401, 403}


def test_safe_owner_order_executes_in_one_request(_client):  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Analyze the organization and produce a verified operating brief"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_required"] is False
    assert body["status"] in {"completed", "partial"}
    assert body["command_id"]
    assert body["executed_steps"] > 0
    assert body["evidence_url"].endswith(f"/{body['command_id']}/brief")


def test_sensitive_owner_order_pauses_for_confirmation(_client):  # noqa: F811
    client = _client
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/organizations/{organization_id}/gpt/operate",
        headers=headers,
        json={"order": "Deploy this release to production and notify the owner by email"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approval_required"
    assert body["approval_required"] is True
    assert "production_change" in body["risk_reasons"]
    assert "external_communication" in body["risk_reasons"]
    assert body["executed_steps"] == 0
