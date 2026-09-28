import base64
import hashlib
import hmac

import pytest

from services.live_media.turn_credentials import (
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
