import base64
import hashlib
import hmac

import pytest

from services.live_media.turn_credentials import (
    CloudflareTurnError,
    issue_cloudflare_turn_credentials,
    issue_turn_credentials,
    validate_turn_urls,
)


def test_coturn_rest_credentials_use_expiring_username_and_hmac_sha1():
    secret = "s" * 48
    result = issue_turn_credentials(
        ["turns:relay.example.test:5349?transport=tcp"],
        secret,
        subject="session_123",
        ttl_seconds=600,
        now=1_700_000_000,
    )

    server = result["ice_servers"][0]
    username = "1700000600:session_123"
    expected = base64.b64encode(
        hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    ).decode("ascii")
    assert result["expires_at"] == 1_700_000_600
    assert server == {
        "urls": ["turns:relay.example.test:5349?transport=tcp"],
        "username": username,
        "credential": expected,
    }


@pytest.mark.parametrize(
    ("urls", "secret", "subject", "ttl"),
    [
        (["https://relay.example.test"], "s" * 32, "session", 600),
        (["turn:relay.example.test:70000"], "s" * 32, "session", 600),
        (["turn:relay.example.test"], "short", "session", 600),
        (["turn:relay.example.test"], "s" * 32, "bad:subject", 600),
        (["turn:relay.example.test"], "s" * 32, "session", 59),
        (["turn:relay.example.test"], "s" * 32, "session", 86_701),
    ],
)
def test_turn_credentials_reject_invalid_configuration(urls, secret, subject, ttl):
    with pytest.raises(ValueError):
        issue_turn_credentials(
            urls,
            secret,
            subject=subject,
            ttl_seconds=ttl,
            now=1_700_000_000,
        )


def test_turn_url_parser_accepts_bracketed_ipv6():
    assert validate_turn_urls(["turn:[2001:db8::1]:3478?transport=udp"]) == [
        "turn:[2001:db8::1]:3478?transport=udp"
    ]



def test_cloudflare_turn_credentials_are_short_lived_and_server_issued(monkeypatch):
    import json

    from services.live_media import turn_credentials

    response_payload = {
        "iceServers": [
            {"urls": ["stun:stun.cloudflare.com:3478"]},
            {
                "urls": ["turn:turn.cloudflare.com:3478?transport=udp"],
                "username": "temporary-user",
                "credential": "temporary-password",
            },
        ]
    }
    calls = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps(response_payload).encode("utf-8")

    def fake_urlopen(request, *, timeout):
        calls["url"] = request.full_url
        calls["authorization"] = request.get_header("Authorization")
        calls["body"] = json.loads(request.data.decode("utf-8"))
        calls["timeout"] = timeout
        return Response()

    monkeypatch.setattr(turn_credentials, "urlopen", fake_urlopen)
    result = issue_cloudflare_turn_credentials(
        "a" * 32,
        "t" * 64,
        ttl_seconds=3900,
    )

    assert calls["url"] == (
        "https://rtc.live.cloudflare.com/v1/turn/keys/"
        + "a" * 32
        + "/credentials/generate-ice-servers"
    )
    assert calls["authorization"] == "Bearer " + "t" * 64
    assert calls["body"] == {"ttl": 3900}
    assert calls["timeout"] == 10.0
    assert result["ice_servers"][0] == {
        "urls": ["stun:stun.cloudflare.com:3478"]
    }
    assert result["ice_servers"][1] == {
        "urls": ["turn:turn.cloudflare.com:3478?transport=udp"],
        "username": "temporary-user",
        "credential": "temporary-password",
    }
    assert result["expires_at"] > 0
    assert "t" * 64 not in repr(result)


def test_cloudflare_turn_rejects_untrusted_or_incomplete_server_response(monkeypatch):
    import json

    from services.live_media import turn_credentials

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps(
                {
                    "iceServers": [
                        {"urls": ["stun:evil.example.test:3478"]},
                        {
                            "urls": ["turn:turn.cloudflare.com:3478?transport=udp"],
                            "username": "temporary-user",
                            "credential": "temporary-password",
                        },
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr(turn_credentials, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(CloudflareTurnError):
        issue_cloudflare_turn_credentials("a" * 32, "t" * 64)


@pytest.mark.parametrize(
    ("key_id", "api_token"),
    [
        ("not-a-key-id", "t" * 64),
        ("a" * 32, "short"),
    ],
)
def test_cloudflare_turn_rejects_invalid_server_credentials(key_id, api_token):
    with pytest.raises(ValueError):
        issue_cloudflare_turn_credentials(key_id, api_token)
