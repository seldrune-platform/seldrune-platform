from tests.test_autonomous_execution import register_owner

pytest_plugins = ["tests.test_autonomous_execution"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _invite_member(client, organization_id, headers, email: str, role: str = "member"):
    invited = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=headers,
        json={"email": email, "role": role, "expires_in_hours": 24},
    )
    assert invited.status_code == 201
    return client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": invited.json()["token"],
            "display_name": role.title() + " User",
            "password": "member-password-123",
        },
    )


def test_standalone_mail_page_is_publicly_reachable(client) -> None:
    response = client.get("/mail")
    assert response.status_code == 200
    assert "Seldrune Mail" in response.text
    assert "/mail-assets/mail.js" in response.text
    assert "Draft with Seldrune AI" in response.text


def test_owners_share_all_mailboxes_and_members_need_explicit_access(client) -> None:
    owner_token, organization_id = register_owner(client)
    owner_headers = _headers(owner_token)
    base = f"/api/v1/organizations/{organization_id}/mail"

    setup = client.post(base + "/setup", headers=owner_headers, json={})
    assert setup.status_code == 201
    assert setup.json()["delivery"]["ready"] is False
    assert {item["email_address"] for item in setup.json()["mailboxes"]} == {
        "you@seldrune.in",
        "hello@seldrune.in",
        "business@seldrune.in",
        "careers@seldrune.in",
    }
    hello = next(
        item
        for item in setup.json()["mailboxes"]
        if item["email_address"] == "hello@seldrune.in"
    )

    accepted = _invite_member(
        client,
        organization_id,
        owner_headers,
        "mail-member@example.com",
    )
    assert accepted.status_code == 201
    member_headers = _headers(accepted.json()["access_token"])

    member_workspace = client.get(base + "/workspace", headers=member_headers)
    assert member_workspace.status_code == 200
    assert member_workspace.json()["mailboxes"] == []
    denied = client.get(
        f"{base}/mailboxes/{hello['id']}/drafts",
        headers=member_headers,
    )
    assert denied.status_code == 403

    shared = client.post(
        f"{base}/mailboxes/{hello['id']}/access",
        headers=owner_headers,
        json={"email": "mail-member@example.com", "permission": "write"},
    )
    assert shared.status_code == 201
    assert shared.json()["permission"] == "write"
    owner_workspace = client.get(base + "/workspace", headers=owner_headers)
    hello_owner_view = next(
        item for item in owner_workspace.json()["mailboxes"] if item["id"] == hello["id"]
    )
    assert hello_owner_view["shared_with"][0]["email"] == "mail-member@example.com"

    member_workspace = client.get(base + "/workspace", headers=member_headers)
    assert [item["email_address"] for item in member_workspace.json()["mailboxes"]] == [
        "hello@seldrune.in"
    ]

    saved = client.post(
        f"{base}/mailboxes/{hello['id']}/drafts",
        headers=member_headers,
        json={
            "to": ["recipient@example.com"],
            "subject": "Welcome",
            "body": "A private draft",
        },
    )
    assert saved.status_code == 201
    assert saved.json()["body"] == "A private draft"
    updated = client.put(
        f"{base}/mailboxes/{hello['id']}/drafts/{saved.json()['id']}",
        headers=member_headers,
        json={
            "to": ["recipient@example.com"],
            "subject": "Welcome updated",
            "body": "Revised private draft",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["body"] == "Revised private draft"

    owner_drafts = client.get(
        f"{base}/mailboxes/{hello['id']}/drafts",
        headers=owner_headers,
    )
    assert owner_drafts.status_code == 200
    assert owner_drafts.json()[0]["subject"] == "Welcome updated"

    outsider = _invite_member(
        client,
        organization_id,
        owner_headers,
        "mail-reader@example.com",
    )
    outsider_headers = _headers(outsider.json()["access_token"])
    read_share = client.post(
        f"{base}/mailboxes/{hello['id']}/access",
        headers=owner_headers,
        json={"email": "mail-reader@example.com", "permission": "read"},
    )
    assert read_share.status_code == 201
    read_only = client.post(
        f"{base}/mailboxes/{hello['id']}/drafts",
        headers=outsider_headers,
        json={"to": ["recipient@example.com"], "subject": "Denied"},
    )
    assert read_only.status_code == 403


def test_domain_verification_checks_real_txt_record(client, monkeypatch) -> None:
    from backend.app.api.routes import mail

    owner_token, organization_id = register_owner(client)
    headers = _headers(owner_token)
    base = f"/api/v1/organizations/{organization_id}/mail"

    added = client.post(
        base + "/domains",
        headers=headers,
        json={"domain": "team.seldrune.in"},
    )
    assert added.status_code == 201
    record = added.json()["verification_record_value"]

    class DNSResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"Answer": [{"data": '"' + record + '"'}]}

    monkeypatch.setattr(mail.httpx, "get", lambda *args, **kwargs: DNSResponse())
    verified = client.post(
        base + "/domains/" + added.json()["id"] + "/verify",
        headers=headers,
        json={},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
