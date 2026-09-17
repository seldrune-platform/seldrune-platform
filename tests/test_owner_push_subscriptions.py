import pytest
from pydantic import ValidationError

from backend.app.api.routes.owner_push import OwnerPushSubscriptionCreate, _endpoint_hash


def test_owner_push_registry_routes_are_explicit(client) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]

    config = paths["/api/v1/organizations/{organization_id}/owner-push/config"]
    registry = paths["/api/v1/organizations/{organization_id}/owner-push/subscriptions"]
    subscription = paths[
        "/api/v1/organizations/{organization_id}/owner-push/subscriptions/{subscription_id}"
    ]

    assert set(config) == {"get"}
    assert set(registry) == {"get", "post"}
    assert set(subscription) == {"delete"}


def test_owner_push_subscription_input_requires_https() -> None:
    with pytest.raises(ValidationError):
        OwnerPushSubscriptionCreate(
            endpoint="http://push.example.test/subscription",
            keys={"p256dh": "a" * 64, "auth": "b" * 16},
        )


def test_owner_push_endpoint_fingerprint_is_stable_and_non_reversible() -> None:
    endpoint = "https://push.example.test/subscriptions/device-token"
    fingerprint = _endpoint_hash(endpoint)

    assert len(fingerprint) == 64
    assert fingerprint == _endpoint_hash(endpoint)
    assert endpoint not in fingerprint


def test_owner_console_loads_separate_push_registry_asset(client) -> None:
    page = client.get("/console")
    script = client.get("/console-assets/owner-push-subscriptions.js")

    assert page.status_code == 200
    assert "/console-assets/owner-push-subscriptions.js" in page.text
    assert script.status_code == 200
    assert "'PushManager' in window" in script.text
    assert "registration.pushManager.subscribe" in script.text
    assert "applicationServerKey" in script.text
    assert "/owner-push/config" in script.text
    assert "/owner-push/subscriptions" in script.text
    assert "method:'POST'" in script.text
    assert "method:'DELETE'" in script.text
    assert "subscription.unsubscribe()" in script.text
    assert "/owner-commands" not in script.text
    assert "/execute" not in script.text
    assert "/approve" not in script.text


def test_owner_push_registry_does_not_add_delivery_provider(client) -> None:
    script = client.get("/console-assets/owner-push-subscriptions.js")
    worker = client.get("/owner-alert-worker.js")

    assert script.status_code == 200
    assert worker.status_code == 200
    assert "webpush" not in script.text.lower()
    assert "vapid_private" not in script.text.lower()
    assert "fetch(" not in worker.text
    assert "addEventListener('push'" in worker.text
