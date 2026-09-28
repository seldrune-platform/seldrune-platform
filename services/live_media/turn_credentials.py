"""Short-lived Coturn REST credentials for browser and gateway ICE clients.

Coturn's static-auth-secret is kept in the gateway. Only derived credentials
with an expiry timestamp leave the service.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import math
import re
import time
from typing import Any

MIN_TURN_CREDENTIAL_TTL_SECONDS = 60
DEFAULT_TURN_CREDENTIAL_TTL_SECONDS = 3900
MAX_TURN_CREDENTIAL_TTL_SECONDS = 24 * 60 * 60 + 300
_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)


def validate_turn_urls(urls: Any) -> list[str]:
    """Validate TURN/TURNS URIs in the format accepted by WebRTC clients."""
    if not isinstance(urls, list) or not urls:
        raise ValueError("TURN URL configuration must be a nonempty JSON array")
    result: list[str] = []
    for url in urls:
        if not isinstance(url, str) or not url or url != url.strip():
            raise ValueError("each TURN URL must be a nonempty string")
        if any(ord(char) < 33 or ord(char) == 127 for char in url):
            raise ValueError("TURN URLs cannot contain whitespace or control characters")
        scheme, separator, remainder = url.partition(":")
        if not separator or scheme.lower() not in {"turn", "turns"}:
            raise ValueError("TURN URLs must use turn: or turns:")
        server, query_separator, query = remainder.partition("?")
        if not server or any(char in server for char in "/#@"):
            raise ValueError("TURN URL must contain a host and optional port")
        port_text: str | None = None
        if server.startswith("["):
            match = re.fullmatch(r"\[([0-9A-Fa-f:.]+)\](?::([0-9]{1,5}))?", server)
            if not match:
                raise ValueError("TURN IPv6 hosts must use bracket notation")
            try:
                ipaddress.IPv6Address(match.group(1))
            except ValueError as exc:
                raise ValueError("TURN URL contains an invalid IPv6 host") from exc
            port_text = match.group(2)
        else:
            if server.count(":") > 1:
                raise ValueError("TURN IPv6 hosts must use bracket notation")
            host, colon, possible_port = server.rpartition(":")
            if colon:
                server, port_text = host, possible_port
            if not _HOST_PATTERN.fullmatch(server):
                raise ValueError("TURN URL contains an invalid host")
        if port_text is not None and not 1 <= int(port_text) <= 65535:
            raise ValueError("TURN URL port is outside the valid range")
        if query_separator and query not in {"transport=udp", "transport=tcp"}:
            raise ValueError("TURN URL transport must be udp or tcp")
        if not query_separator and "?" in url:
            raise ValueError("TURN URL query is invalid")
        result.append(url)
    return result


def issue_turn_credentials(
    urls: list[str],
    shared_secret: str,
    *,
    subject: str,
    ttl_seconds: int = DEFAULT_TURN_CREDENTIAL_TTL_SECONDS,
    now: int | float | None = None,
) -> dict[str, Any]:
    """Return Coturn REST API username/password values that expire after the TTL."""
    validated_urls = validate_turn_urls(urls)
    if not isinstance(shared_secret, str) or len(shared_secret.encode("utf-8")) < 32:
        raise ValueError("TURN shared secret must contain at least 32 bytes")
    if not isinstance(subject, str) or not _SUBJECT_PATTERN.fullmatch(subject):
        raise ValueError("TURN credential subject is invalid")
    if (
        isinstance(ttl_seconds, bool)
        or not isinstance(ttl_seconds, int)
        or not (
            MIN_TURN_CREDENTIAL_TTL_SECONDS
            <= ttl_seconds
            <= MAX_TURN_CREDENTIAL_TTL_SECONDS
        )
    ):
        raise ValueError("TURN credential lifetime is outside the supported range")
    if now is None:
        issued_at = int(time.time())
    elif (
        isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(float(now))
        or now < 0
    ):
        raise ValueError("TURN credential issue time is invalid")
    else:
        issued_at = int(now)
    username = f"{issued_at + ttl_seconds}:{subject}"
    digest = hmac.new(
        shared_secret.encode("utf-8"), username.encode("utf-8"), hashlib.sha1
    ).digest()
    credential = base64.b64encode(digest).decode("ascii")
    return {
        "ice_servers": [
            {
                "urls": validated_urls,
                "username": username,
                "credential": credential,
            }
        ],
        "expires_at": issued_at + ttl_seconds,
    }
