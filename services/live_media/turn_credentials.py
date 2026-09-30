"""Short-lived Coturn REST credentials for browser and gateway ICE clients.

Coturn's static-auth-secret is kept in the gateway. Only derived credentials
with an expiry timestamp leave the service.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ipaddress
import math
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MIN_TURN_CREDENTIAL_TTL_SECONDS = 60
DEFAULT_TURN_CREDENTIAL_TTL_SECONDS = 3900
MAX_TURN_CREDENTIAL_TTL_SECONDS = 24 * 60 * 60 + 300
_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CLOUDFLARE_KEY_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
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


class CloudflareTurnError(RuntimeError):
    """A Cloudflare TURN credential could not be safely issued."""


def _validate_cloudflare_ice_servers(
    payload: Any,
    *,
    ttl_seconds: int,
    now: int | float | None = None,
) -> dict[str, Any]:
    """Validate the provider response before forwarding temporary ICE credentials."""
    servers = payload.get("iceServers") if isinstance(payload, dict) else None
    if not isinstance(servers, list) or not servers:
        raise CloudflareTurnError("Cloudflare TURN returned no ICE servers")

    result: list[dict[str, Any]] = []
    has_turn = False
    has_stun = False
    for server in servers:
        if not isinstance(server, dict):
            raise CloudflareTurnError("Cloudflare TURN returned an invalid ICE server")
        urls = server.get("urls")
        if isinstance(urls, str):
            urls = [urls]
        if not isinstance(urls, list) or not urls or any(
            not isinstance(url, str) for url in urls
        ):
            raise CloudflareTurnError("Cloudflare TURN returned invalid ICE URLs")

        validated_urls: list[str] = []
        has_server_turn = False
        has_server_stun = False
        for url in urls:
            if re.fullmatch(
                r"stun:stun\.cloudflare\.com(?::[0-9]{1,5})?",
                url,
                flags=re.IGNORECASE,
            ):
                has_stun = has_server_stun = True
            elif url.lower().startswith(("turn:", "turns:")):
                try:
                    validate_turn_urls([url])
                except ValueError as exc:
                    raise CloudflareTurnError(
                        "Cloudflare TURN returned an invalid relay URL"
                    ) from exc
                authority = url.partition(":")[2].partition("?")[0]
                host = authority.split(":", 1)[0].lower()
                if host != "turn.cloudflare.com":
                    raise CloudflareTurnError(
                        "Cloudflare TURN returned an unexpected relay host"
                    )
                has_turn = has_server_turn = True
            else:
                raise CloudflareTurnError(
                    "Cloudflare TURN returned an unexpected ICE server"
                )
            validated_urls.append(url)

        username = server.get("username")
        credential = server.get("credential")
        if has_server_turn:
            if (
                not isinstance(username, str)
                or not username
                or not isinstance(credential, str)
                or not credential
            ):
                raise CloudflareTurnError(
                    "Cloudflare TURN returned incomplete relay credentials"
                )
            result.append(
                {"urls": validated_urls, "username": username, "credential": credential}
            )
        else:
            if username is not None or credential is not None:
                raise CloudflareTurnError(
                    "Cloudflare STUN response unexpectedly included credentials"
                )
            result.append({"urls": validated_urls})

    if not has_turn or not has_stun:
        raise CloudflareTurnError("Cloudflare TURN response must include STUN and TURN")
    if now is None:
        issued_at = int(time.time())
    elif (
        isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(float(now))
        or now < 0
    ):
        raise CloudflareTurnError("Cloudflare TURN issue time is invalid")
    else:
        issued_at = int(now)
    return {"ice_servers": result, "expires_at": issued_at + ttl_seconds}


def issue_cloudflare_turn_credentials(
    turn_key_id: str,
    api_token: str,
    *,
    ttl_seconds: int = DEFAULT_TURN_CREDENTIAL_TTL_SECONDS,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Request short-lived ICE credentials from Cloudflare using a server-only key."""
    if (
        not isinstance(turn_key_id, str)
        or not _CLOUDFLARE_KEY_ID_PATTERN.fullmatch(turn_key_id)
    ):
        raise ValueError("Cloudflare TURN key ID is invalid")
    if not isinstance(api_token, str) or len(api_token.encode("utf-8")) < 32:
        raise ValueError("Cloudflare TURN API token must contain at least 32 bytes")
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
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0 < timeout_seconds <= 30
    ):
        raise ValueError("TURN provider timeout is outside the supported range")

    url = (
        "https://rtc.live.cloudflare.com/v1/turn/keys/"
        f"{turn_key_id}/credentials/generate-ice-servers"
    )
    request = Request(
        url,
        data=json.dumps({"ttl": ttl_seconds}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=float(timeout_seconds)) as response:
            status_code = getattr(response, "status", 200)
            raw = response.read(65_537)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CloudflareTurnError(
            "Cloudflare TURN credential request failed"
        ) from exc
    if status_code not in {200, 201} or len(raw) > 65_536:
        raise CloudflareTurnError("Cloudflare TURN credential request was rejected")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudflareTurnError(
            "Cloudflare TURN returned an invalid response"
        ) from exc
    return _validate_cloudflare_ice_servers(payload, ttl_seconds=ttl_seconds)
