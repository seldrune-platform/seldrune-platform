from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.api.dependencies import SessionDep
from backend.app.api.routes import auth as auth_routes
from backend.app.api.routes import owner_commands
from backend.app.core.config import settings
from backend.app.core.rbac import Role
from backend.app.core.security import access_token_fingerprint
from backend.app.models.membership import Membership
from backend.app.models.mcp_oauth import MCPAuthorizationCode, MCPOAuthClient, MCPRefreshToken
from backend.app.models.deepfacelive_bridge import (
    DeepFaceLiveAgent,
    DeepFaceLiveCommand,
    DeepFaceLivePairingCode,
)
from backend.app.models.organization import Organization
from backend.app.models.revoked_access_token import RevokedAccessToken
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest
from backend.app.schemas.orchestration import (
    AutonomousExecutionRequest,
    OrchestrationCreate,
)
from backend.app.services.audit import record_audit

logger = logging.getLogger(__name__)
router = APIRouter(tags=["owner-console-mcp"])

LOGIN_COOKIE = "seldrune_mcp_login"
CSRF_COOKIE = "seldrune_mcp_csrf"
OWNER_SCOPE = "seldrune.owner"
DEEPFACELIVE_SCOPE = "seldrune.deepfacelive"
OFFLINE_SCOPE = "offline_access"
SUPPORTED_SCOPES = {OWNER_SCOPE, DEEPFACELIVE_SCOPE, OFFLINE_SCOPE}
SUPPORTED_PROTOCOLS = {"2025-03-26", "2025-06-18", "2025-11-25"}
MAX_REQUEST_BYTES = 1_000_000
TOKEN_LIFETIME_SECONDS = 15 * 60
AUTHORIZATION_CODE_LIFETIME_SECONDS = 5 * 60
LOGIN_TICKET_LIFETIME_SECONDS = 5 * 60


@dataclass(frozen=True)
class AuthorizationRequest:
    client_id: str
    redirect_uri: str
    state: str
    code_challenge: str
    resource: str
    scope: str


class OAuthRequestError(ValueError):
    pass


def _issuer() -> str:
    parsed = urlsplit(settings.public_app_url.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise RuntimeError("SELDRUNE_PUBLIC_APP_URL must be an absolute HTTP(S) URL")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("SELDRUNE_PUBLIC_APP_URL must contain only an origin")
    return f"{parsed.scheme}://{parsed.netloc}"


def _resource_url() -> str:
    return f"{_issuer()}/mcp"


def _oauth_url(path: str) -> str:
    return f"{_issuer()}{path}"


def _secure_cookies() -> bool:
    return _issuer().startswith("https://")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _csrf_valid(request: Request, submitted: str) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    return bool(cookie and submitted and secrets.compare_digest(cookie, submitted))


def _set_csrf_cookie(response: Response, value: str | None = None) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        value or secrets.token_urlsafe(32),
        max_age=600,
        httponly=True,
        secure=_secure_cookies(),
        samesite="strict",
        path="/oauth/authorize",
    )


def _clear_oauth_cookies(response: Response) -> None:
    response.delete_cookie(
        CSRF_COOKIE, path="/oauth/authorize", secure=_secure_cookies(), samesite="strict"
    )
    response.delete_cookie(
        LOGIN_COOKIE, path="/oauth/authorize", secure=_secure_cookies(), samesite="strict"
    )


def _hidden_fields(params: AuthorizationRequest) -> str:
    values = {
        "response_type": "code",
        "client_id": params.client_id,
        "redirect_uri": params.redirect_uri,
        "state": params.state,
        "code_challenge": params.code_challenge,
        "code_challenge_method": "S256",
        "resource": params.resource,
        "scope": params.scope,
    }
    return "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value, quote=True)}">'
        for key, value in values.items()
    )


def _page(title: str, content: str, *, status_code: int = 200) -> HTMLResponse:
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:light dark}}
body{{font:16px/1.5 system-ui,sans-serif;max-width:520px;margin:8vh auto;padding:0 20px}}
main{{border:1px solid #8886;border-radius:14px;padding:24px}}
label{{display:block;margin:14px 0 5px}}
input{{box-sizing:border-box;width:100%;padding:11px;border:1px solid #8888;border-radius:7px}}
button{{margin-top:20px;padding:11px 16px;border:0;border-radius:7px;cursor:pointer;
font-weight:650}}
small{{color:#888}}.error{{color:#b3261e}}.scope{{padding:12px;background:#8881;border-radius:8px}}
</style></head><body><main><h1>{html.escape(title)}</h1>{content}</main></body></html>"""
    return HTMLResponse(
        body,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _query_string(params: AuthorizationRequest) -> str:
    return urlencode(
        {
            "response_type": "code",
            "client_id": params.client_id,
            "redirect_uri": params.redirect_uri,
            "state": params.state,
            "code_challenge": params.code_challenge,
            "code_challenge_method": "S256",
            "resource": params.resource,
            "scope": params.scope,
        }
    )


def _binding(params: AuthorizationRequest) -> str:
    value = {
        "client_id": params.client_id,
        "redirect_uri": params.redirect_uri,
        "state": params.state,
        "code_challenge": params.code_challenge,
        "resource": params.resource,
        "scope": params.scope,
    }
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _parse_authorization_request(values: Any) -> AuthorizationRequest:
    if hasattr(values, "getlist"):
        for key in (
            "response_type",
            "client_id",
            "redirect_uri",
            "state",
            "code_challenge",
            "code_challenge_method",
            "resource",
            "scope",
        ):
            if len(values.getlist(key)) > 1:
                raise OAuthRequestError("Duplicate OAuth request parameters are not supported.")
    response_type = str(values.get("response_type", ""))
    client_id = str(values.get("client_id", ""))
    redirect_uri = str(values.get("redirect_uri", ""))
    state = str(values.get("state", ""))
    challenge = str(values.get("code_challenge", ""))
    challenge_method = str(values.get("code_challenge_method", ""))
    resource = str(values.get("resource") or _resource_url())
    scope = str(values.get("scope") or f"{OWNER_SCOPE} {OFFLINE_SCOPE}")
    scopes = scope.split()

    if response_type != "code":
        raise OAuthRequestError("Only the authorization code flow is supported.")
    if not client_id or len(client_id) > 96:
        raise OAuthRequestError("The OAuth client is invalid.")
    if not redirect_uri or len(redirect_uri) > 2048:
        raise OAuthRequestError("The redirect URL is invalid.")
    if not state or len(state) > 512:
        raise OAuthRequestError("A valid state value is required.")
    if challenge_method != "S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
        raise OAuthRequestError("PKCE with S256 is required.")
    if resource != _resource_url():
        raise OAuthRequestError("The requested resource does not match this server.")
    permission_scopes = set(scopes) & {OWNER_SCOPE, DEEPFACELIVE_SCOPE}
    if len(permission_scopes) != 1 or len(scopes) != len(set(scopes)):
        raise OAuthRequestError("Request exactly one supported Seldrune permission scope.")
    if set(scopes) - SUPPORTED_SCOPES:
        raise OAuthRequestError("The requested scope is not supported.")
    return AuthorizationRequest(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
        resource=resource,
        scope=" ".join(scopes),
    )


def _redirect_uri_allowed(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password or parsed.fragment or not parsed.netloc:
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1", "::1"}


def _get_client(session: Session, client_id: str, redirect_uri: str) -> MCPOAuthClient:
    client = session.get(MCPOAuthClient, client_id)
    if (
        client is None
        or client.token_endpoint_auth_method != "none"
        or redirect_uri not in client.redirect_uris
    ):
        raise OAuthRequestError("The OAuth client or redirect URL is invalid.")
    return client


def _has_owner_membership(session: Session, user_id: UUID) -> bool:
    return (
        session.scalar(
            select(Membership.organization_id)
            .where(
                Membership.user_id == user_id,
                Membership.role == Role.OWNER.value,
            )
            .limit(1)
        )
        is not None
    )


def _login_ticket(ticket: str, params: AuthorizationRequest) -> UUID | None:
    try:
        payload = jwt.decode(ticket, settings.auth_secret_key, algorithms=["HS256"])
        if (
            payload.get("purpose") != "mcp_oauth_login"
            or payload.get("request") != _binding(params)
        ):
            return None
        return UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def _login_form(
    params: AuthorizationRequest,
    csrf: str,
    client_name: str,
    error: str = "",
) -> HTMLResponse:
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    body = f"""
<p>Sign in to Seldrune to connect
<strong>{html.escape(client_name)}</strong> to the Owner Console.</p>
{err}
<form method="post" action="/oauth/authorize/login" autocomplete="on">
<input type="hidden" name="csrf_token" value="{html.escape(csrf, quote=True)}">
{_hidden_fields(params)}
<label for="email">Email</label>
<input id="email" name="email" type="email" autocomplete="username" required>
<label for="password">Password</label>
<input id="password" name="password" type="password"
autocomplete="current-password" required>
<label for="mfa_code">Authenticator code <small>(if enabled)</small></label>
<input id="mfa_code" name="mfa_code" inputmode="numeric" autocomplete="one-time-code">
<label for="recovery_code">Recovery code <small>(use instead of authenticator code)</small></label>
<input id="recovery_code" name="recovery_code" autocomplete="off">
<button type="submit">Continue</button>
</form>
<p><small>Your password is sent only to your Seldrune service.</small></p>
"""
    response = _page("Connect Seldrune", body)
    _set_csrf_cookie(response, csrf)
    return response


def _consent_form(
    params: AuthorizationRequest,
    csrf: str,
    client_name: str,
    user: User,
) -> HTMLResponse:
    if DEEPFACELIVE_SCOPE in params.scope.split():
        scope_html = (
            '<div class="scope"><strong>DeepFaceLive companion access</strong><br>'
            "Read the paired computer's app status and queue DeepFaceLive start or stop "
            "commands. Camera frames, audio, models, and video are not uploaded or relayed."
            "</div>"
        )
    else:
        scope_html = (
            '<div class="scope"><strong>Owner Console access</strong><br>'
            "Read owner dashboard, audit events, and command status; change governance "
            "policy; create commands, approve them, execute them, promote outcomes, and "
            "create recovery commands as separate actions. Seldrune checks your Owner "
            "role on every call."
            "</div>"
        )
    if OFFLINE_SCOPE in params.scope.split():
        scope_html += (
            '<p class="scope"><strong>Stay connected</strong><br>'
            "Allow the client to renew its connection until you revoke access.</p>"
        )
    body = f"""
<p><strong>{html.escape(client_name)}</strong> is requesting access for
{html.escape(user.email)}.</p>
{scope_html}
<form method="post" action="/oauth/authorize/consent">
<input type="hidden" name="csrf_token" value="{html.escape(csrf, quote=True)}">
{_hidden_fields(params)}
<button type="submit" name="decision" value="allow">Allow</button>
<button type="submit" name="decision" value="deny">Deny</button>
</form>
"""
    response = _page("Review Seldrune access", body)
    _set_csrf_cookie(response, csrf)
    return response


def _authorization_redirect(params: AuthorizationRequest, **values: str) -> RedirectResponse:
    query = {
        "state": params.state,
        "iss": _issuer(),
        **values,
    }
    parsed = urlsplit(params.redirect_uri)
    existing = parsed.query
    appended = urlencode(query)
    return RedirectResponse(
        urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                f"{existing}&{appended}" if existing else appended,
                "",
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata() -> dict[str, Any]:
    issuer = _issuer()
    return {
        "issuer": issuer,
        "authorization_endpoint": _oauth_url("/oauth/authorize"),
        "token_endpoint": _oauth_url("/oauth/token"),
        "registration_endpoint": _oauth_url("/oauth/register"),
        "revocation_endpoint": _oauth_url("/oauth/revoke"),
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": sorted(SUPPORTED_SCOPES),
    }


@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata() -> dict[str, Any]:
    return {
        "resource": _resource_url(),
        "authorization_servers": [_issuer()],
        "scopes_supported": [OWNER_SCOPE, DEEPFACELIVE_SCOPE],
        "bearer_methods_supported": ["header"],
    }


@router.post("/oauth/register")
async def register_oauth_client(request: Request, session: SessionDep) -> JSONResponse:
    if int(request.headers.get("content-length", "0") or "0") > 32_000:
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)

    redirect_uris = body.get("redirect_uris")
    if (
        not isinstance(redirect_uris, list)
        or not 1 <= len(redirect_uris) <= 10
        or any(
            not isinstance(uri, str)
            or len(uri) > 2048
            or not _redirect_uri_allowed(uri)
            for uri in redirect_uris
        )
        or len(set(redirect_uris)) != len(redirect_uris)
    ):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)

    auth_method = body.get("token_endpoint_auth_method", "none")
    grant_types = body.get("grant_types", ["authorization_code", "refresh_token"])
    response_types = body.get("response_types", ["code"])
    if (
        auth_method != "none"
        or not isinstance(grant_types, list)
        or set(grant_types) != {"authorization_code", "refresh_token"}
        or not isinstance(response_types, list)
        or set(response_types) != {"code"}
    ):
        return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)

    client_name = str(body.get("client_name") or "MCP client").strip()[:200] or "MCP client"
    client_id = secrets.token_urlsafe(32)
    session.add(
        MCPOAuthClient(
            client_id=client_id,
            client_name=client_name,
            redirect_uris=redirect_uris,
            token_endpoint_auth_method="none",
        )
    )
    session.commit()
    return JSONResponse(
        {
            "client_id": client_id,
            "client_id_issued_at": int(_now().timestamp()),
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/oauth/authorize")
def authorize(request: Request, session: SessionDep) -> Response:
    try:
        params = _parse_authorization_request(request.query_params)
        client = _get_client(session, params.client_id, params.redirect_uri)
    except OAuthRequestError as exc:
        return _page("Unable to connect", f"<p>{html.escape(str(exc))}</p>", status_code=400)

    ticket = request.cookies.get(LOGIN_COOKIE, "")
    user_id = _login_ticket(ticket, params) if ticket else None
    user = session.get(User, user_id) if user_id else None
    csrf = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)

    if user is None or not user.is_active:
        response = _login_form(params, csrf, client.client_name)
        if ticket:
            response.delete_cookie(
                LOGIN_COOKIE,
                path="/oauth/authorize",
                secure=_secure_cookies(),
                samesite="strict",
            )
        return response
    if not _has_owner_membership(session, user.id):
        response = _page(
            "Owner access required",
            "<p>This Seldrune account does not have the Owner role for an organization.</p>",
            status_code=403,
        )
        _clear_oauth_cookies(response)
        return response

    response = _consent_form(params, csrf, client.client_name, user)
    return response


@router.post("/oauth/authorize/login")
async def authorize_login(request: Request, session: SessionDep) -> Response:
    form = await request.form()
    values = dict(form)
    try:
        params = _parse_authorization_request(values)
        client = _get_client(session, params.client_id, params.redirect_uri)
    except OAuthRequestError as exc:
        return _page("Unable to connect", f"<p>{html.escape(str(exc))}</p>", status_code=400)

    csrf = str(values.get("csrf_token") or "")
    if not _csrf_valid(request, csrf):
        return _login_form(
            params,
            secrets.token_urlsafe(32),
            client.client_name,
            "This sign-in expired. Please try again.",
        )

    try:
        payload = LoginRequest(
            email=str(values.get("email") or ""),
            password=str(values.get("password") or ""),
            mfa_code=str(values.get("mfa_code") or "") or None,
            recovery_code=str(values.get("recovery_code") or "") or None,
        )
        auth_response = auth_routes.login(payload, request, session)
    except ValidationError:
        return _login_form(params, csrf, client.client_name, "Enter a valid email and password.")
    except HTTPException as exc:
        if exc.status_code == 429:
            detail = "Too many sign-in attempts. Wait before trying again."
        else:
            detail = "Sign-in failed. Check your credentials and MFA code."
        return _login_form(params, csrf, client.client_name, detail)
    except Exception:
        session.rollback()
        logger.exception("Seldrune OAuth login failed")
        return _login_form(params, csrf, client.client_name, "Sign-in could not be completed.")

    user_id = auth_response.user.id
    try:
        auth_routes.logout(auth_response.access_token, session)
    except Exception:
        session.rollback()
        logger.exception("Could not retire temporary Seldrune login credentials")
        return _login_form(params, csrf, client.client_name, "Sign-in could not be completed.")

    now = _now()
    login_ticket = jwt.encode(
        {
            "sub": str(user_id),
            "purpose": "mcp_oauth_login",
            "request": _binding(params),
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=LOGIN_TICKET_LIFETIME_SECONDS),
        },
        settings.auth_secret_key,
        algorithm="HS256",
    )
    response = RedirectResponse(
        f"/oauth/authorize?{_query_string(params)}",
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    response.set_cookie(
        LOGIN_COOKIE,
        login_ticket,
        max_age=LOGIN_TICKET_LIFETIME_SECONDS,
        httponly=True,
        secure=_secure_cookies(),
        samesite="strict",
        path="/oauth/authorize",
    )
    return response


@router.post("/oauth/authorize/consent")
async def authorize_consent(request: Request, session: SessionDep) -> Response:
    form = await request.form()
    values = dict(form)
    try:
        params = _parse_authorization_request(values)
        client = _get_client(session, params.client_id, params.redirect_uri)
    except OAuthRequestError as exc:
        return _page("Unable to connect", f"<p>{html.escape(str(exc))}</p>", status_code=400)

    csrf = str(values.get("csrf_token") or "")
    if not _csrf_valid(request, csrf):
        response = _page(
            "Sign-in expired",
            "<p>Restart the connection and review it again.</p>",
            status_code=400,
        )
        _clear_oauth_cookies(response)
        return response

    user_id = _login_ticket(request.cookies.get(LOGIN_COOKIE, ""), params)
    user = session.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        response = _page(
            "Sign-in expired",
            "<p>Restart the connection and sign in again.</p>",
            status_code=400,
        )
        _clear_oauth_cookies(response)
        return response
    if not _has_owner_membership(session, user.id):
        response = _page(
            "Owner access required",
            "<p>This Seldrune account does not have the Owner role for an organization.</p>",
            status_code=403,
        )
        _clear_oauth_cookies(response)
        return response

    if values.get("decision") != "allow":
        response = _authorization_redirect(
            params,
            error="access_denied",
            error_description="The user denied access.",
        )
        _clear_oauth_cookies(response)
        return response

    raw_code = secrets.token_urlsafe(48)
    session.add(
        MCPAuthorizationCode(
            code_sha256=_sha256(raw_code),
            client_id=client.client_id,
            user_id=user.id,
            redirect_uri=params.redirect_uri,
            resource=params.resource,
            scope=params.scope,
            code_challenge=params.code_challenge,
            code_challenge_method="S256",
            expires_at=_now() + timedelta(seconds=AUTHORIZATION_CODE_LIFETIME_SECONDS),
        )
    )
    record_audit(
        session,
        actor_user_id=user.id,
        action="mcp.oauth_authorized",
        resource_type="oauth_client",
        resource_id=client.client_id,
        details={"client_name": client.client_name, "scope": params.scope},
    )
    session.commit()
    response = _authorization_redirect(params, code=raw_code)
    _clear_oauth_cookies(response)
    return response


def _invalid_oauth(error: str) -> JSONResponse:
    return JSONResponse(
        {"error": error},
        status_code=400,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _new_refresh_token(
    session: Session,
    *,
    user_id: UUID,
    client_id: str,
    resource: str,
    scope: str,
    family_id: UUID | None = None,
) -> str:
    token = secrets.token_urlsafe(48)
    session.add(
        MCPRefreshToken(
            token_sha256=_sha256(token),
            family_id=family_id or uuid4(),
            user_id=user_id,
            client_id=client_id,
            resource=resource,
            scope=scope,
            expires_at=_now() + timedelta(days=settings.auth_refresh_token_days),
        )
    )
    session.flush()
    return token


def _new_access_token(
    *,
    user_id: UUID,
    client_id: str,
    resource: str,
    scope: str,
) -> str:
    now = _now()
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "mcp_access",
            "client_id": client_id,
            "scope": scope,
            "aud": resource,
            "iss": _issuer(),
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=TOKEN_LIFETIME_SECONDS),
        },
        settings.auth_secret_key,
        algorithm="HS256",
    )


def _token_response(
    *,
    user_id: UUID,
    client_id: str,
    resource: str,
    scope: str,
    refresh_token: str,
) -> JSONResponse:
    access_token = _new_access_token(
        user_id=user_id,
        client_id=client_id,
        resource=resource,
        scope=scope,
    )
    return JSONResponse(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME_SECONDS,
            "refresh_token": refresh_token,
            "scope": scope,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/oauth/token")
async def exchange_oauth_token(request: Request, session: SessionDep) -> Response:
    if request.headers.get("authorization"):
        return _invalid_oauth("invalid_client")
    form = await request.form()
    values = dict(form)
    grant_type = str(values.get("grant_type") or "")
    client_id = str(values.get("client_id") or "")
    if not client_id or len(client_id) > 96:
        return _invalid_oauth("invalid_client")
    client = session.get(MCPOAuthClient, client_id)
    if client is None or client.token_endpoint_auth_method != "none":
        return _invalid_oauth("invalid_client")

    if grant_type == "authorization_code":
        raw_code = str(values.get("code") or "")
        redirect_uri = str(values.get("redirect_uri") or "")
        verifier = str(values.get("code_verifier") or "")
        if (
            not raw_code
            or len(raw_code) > 512
            or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier)
        ):
            return _invalid_oauth("invalid_grant")
        statement = select(MCPAuthorizationCode).where(
            MCPAuthorizationCode.code_sha256 == _sha256(raw_code)
        )
        if session.get_bind().dialect.name != "sqlite":
            statement = statement.with_for_update()
        grant = session.scalar(statement)
        if (
            grant is None
            or grant.consumed_at is not None
            or _aware(grant.expires_at) <= _now()
            or grant.client_id != client_id
            or grant.redirect_uri != redirect_uri
            or (
                values.get("resource") is not None
                and str(values.get("resource")) != grant.resource
            )
        ):
            return _invalid_oauth("invalid_grant")
        verifier_challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        if not secrets.compare_digest(verifier_challenge, grant.code_challenge):
            return _invalid_oauth("invalid_grant")
        user = session.get(User, grant.user_id)
        if user is None or not user.is_active:
            return _invalid_oauth("invalid_grant")

        grant.consumed_at = _now()
        refresh_token = _new_refresh_token(
            session,
            user_id=user.id,
            client_id=client_id,
            resource=grant.resource,
            scope=grant.scope,
        )
        result = _token_response(
            user_id=user.id,
            client_id=client_id,
            resource=grant.resource,
            scope=grant.scope,
            refresh_token=refresh_token,
        )
        session.commit()
        return result

    if grant_type == "refresh_token":
        raw_refresh = str(values.get("refresh_token") or "")
        if (
            not raw_refresh
            or len(raw_refresh) > 512
            or (
                values.get("resource") is not None
                and str(values.get("resource")) != _resource_url()
            )
        ):
            return _invalid_oauth("invalid_grant")
        statement = select(MCPRefreshToken).where(
            MCPRefreshToken.token_sha256 == _sha256(raw_refresh)
        )
        if session.get_bind().dialect.name != "sqlite":
            statement = statement.with_for_update()
        grant = session.scalar(statement)
        if grant is None or grant.client_id != client_id:
            return _invalid_oauth("invalid_grant")
        if grant.consumed_at is not None:
            session.execute(
                update(MCPRefreshToken)
                .where(
                    MCPRefreshToken.family_id == grant.family_id,
                    MCPRefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=_now())
            )
            session.commit()
            return _invalid_oauth("invalid_grant")
        if grant.revoked_at is not None or _aware(grant.expires_at) <= _now():
            return _invalid_oauth("invalid_grant")
        user = session.get(User, grant.user_id)
        if user is None or not user.is_active:
            return _invalid_oauth("invalid_grant")

        grant.consumed_at = _now()
        refresh_token = _new_refresh_token(
            session,
            user_id=user.id,
            client_id=grant.client_id,
            resource=grant.resource,
            scope=grant.scope,
            family_id=grant.family_id,
        )
        result = _token_response(
            user_id=user.id,
            client_id=grant.client_id,
            resource=grant.resource,
            scope=grant.scope,
            refresh_token=refresh_token,
        )
        session.commit()
        return result

    return _invalid_oauth("unsupported_grant_type")


@router.post("/oauth/revoke")
async def revoke_oauth_token(request: Request, session: SessionDep) -> Response:
    if request.headers.get("authorization"):
        return _invalid_oauth("invalid_client")
    form = await request.form()
    values = dict(form)
    raw_token = str(values.get("token") or "")
    client_id = str(values.get("client_id") or "")
    if not raw_token or len(raw_token) > 4096:
        return JSONResponse({}, status_code=200, headers={"Cache-Control": "no-store"})

    refresh = session.get(MCPRefreshToken, _sha256(raw_token))
    if refresh is not None and (not client_id or refresh.client_id == client_id):
        session.execute(
            update(MCPRefreshToken)
            .where(
                MCPRefreshToken.family_id == refresh.family_id,
                MCPRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=_now())
        )
        session.commit()
        return JSONResponse({}, status_code=200, headers={"Cache-Control": "no-store"})

    try:
        claims = jwt.decode(
            raw_token,
            settings.auth_secret_key,
            algorithms=["HS256"],
            audience=_resource_url(),
            issuer=_issuer(),
        )
        if claims.get("type") == "mcp_access" and (
            not client_id or claims.get("client_id") == client_id
        ):
            user_id = UUID(str(claims["sub"]))
            expires_at = datetime.fromtimestamp(float(claims["exp"]), tz=UTC)
            fingerprint = access_token_fingerprint(raw_token)
            existing = session.scalar(
                select(RevokedAccessToken.id).where(
                    RevokedAccessToken.token_sha256 == fingerprint
                )
            )
            if existing is None:
                session.add(
                    RevokedAccessToken(
                        user_id=user_id,
                        token_sha256=fingerprint,
                        expires_at=expires_at,
                    )
                )
                session.commit()
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, OverflowError):
        pass
    return JSONResponse({}, status_code=200, headers={"Cache-Control": "no-store"})


def _bearer_challenge(required_scope: str = OWNER_SCOPE) -> str:
    metadata_url = _oauth_url("/.well-known/oauth-protected-resource/mcp")
    return (
        'Bearer error="invalid_token", error_description="Authentication required", '
        f'resource_metadata="{metadata_url}", scope="{required_scope}"'
    )


def _authenticate_mcp_request(
    request: Request,
    session: Session,
    required_scope: str = OWNER_SCOPE,
) -> tuple[User, dict[str, Any]]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 4096:
        raise HTTPException(
            status_code=401,
            detail="Bearer authentication required",
            headers={"WWW-Authenticate": _bearer_challenge(required_scope)},
        )
    try:
        claims = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=["HS256"],
            audience=_resource_url(),
            issuer=_issuer(),
            options={"require": ["sub", "exp", "iat", "jti", "aud", "iss"]},
        )
        if (
            claims.get("type") != "mcp_access"
            or required_scope not in str(claims.get("scope", "")).split()
        ):
            raise jwt.InvalidTokenError("Insufficient MCP access")
        user_id = UUID(str(claims["sub"]))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired bearer token",
            headers={"WWW-Authenticate": _bearer_challenge(required_scope)},
        ) from None

    fingerprint = access_token_fingerprint(token)
    revoked = session.scalar(
        select(RevokedAccessToken.id).where(
            RevokedAccessToken.token_sha256 == fingerprint
        )
    )
    user = session.get(User, user_id)
    if revoked is not None or user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired bearer token",
            headers={"WWW-Authenticate": _bearer_challenge(required_scope)},
        )
    return user, claims


def _owner_membership(
    session: Session,
    user: User,
    organization_id: str,
) -> Membership:
    try:
        org_id = UUID(organization_id)
    except (TypeError, ValueError):
        raise ValueError("organization_id must be a UUID") from None
    membership = session.get(Membership, (org_id, user.id))
    if membership is None or membership.role != Role.OWNER.value:
        raise HTTPException(status_code=403, detail="Seldrune Owner role required")
    return membership


def _safe_payload(value: Any) -> Any:
    sensitive_keys = ("secret", "token", "password", "api_key", "authorization")
    encoded = jsonable_encoder(value)

    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: (
                    "[redacted]"
                    if any(word in str(key).lower() for word in sensitive_keys)
                    else clean(child)
                )
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [clean(child) for child in item]
        return item

    return clean(encoded)


def _json_text(value: Any) -> str:
    text = json.dumps(_safe_payload(value), ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= 300_000 else text[:300_000] + "…[truncated]"


def _field(name: str, description: str, field_type: str = "string") -> dict[str, str]:
    return {"type": field_type, "description": description}


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
    *,
    read_only: bool,
    destructive: bool = False,
    idempotent: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
            "openWorldHint": False,
        },
    }


ORG_ID = _field("organization_id", "Seldrune organization UUID.")
RUN_ID = _field("command_id", "Owner command UUID.")
TOOLS = [
    _tool(
        "list_owner_organizations",
        "List organizations where the authenticated Seldrune user has the Owner role.",
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "get_owner_dashboard",
        "Read the owner dashboard for an organization. The caller must be an Owner.",
        {"organization_id": ORG_ID},
        ["organization_id"],
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "get_governance_policy",
        "Read the current owner governance policy for an organization.",
        {"organization_id": ORG_ID},
        ["organization_id"],
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "preview_governance_policy",
        "Preview policy changes and show which commands or projects would be blocked. "
        "Does not change policy.",
        {
            "organization_id": ORG_ID,
            "max_steps_per_command": _field(
                "max_steps_per_command", "Maximum steps allowed in one command.", "integer"
            ),
            "max_project_budget_usd": _field(
                "max_project_budget_usd", "Maximum project budget in USD.", "number"
            ),
            "allow_autonomous_execution": _field(
                "allow_autonomous_execution",
                "Whether approved owner commands may execute autonomously.",
                "boolean",
            ),
        },
        [
            "organization_id",
            "max_steps_per_command",
            "max_project_budget_usd",
            "allow_autonomous_execution",
        ],
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "update_governance_policy",
        "Update owner governance policy. Review the preview first; changing autonomous "
        "execution can allow approved commands to run.",
        {
            "organization_id": ORG_ID,
            "max_steps_per_command": _field(
                "max_steps_per_command", "Maximum steps allowed in one command.", "integer"
            ),
            "max_project_budget_usd": _field(
                "max_project_budget_usd", "Maximum project budget in USD.", "number"
            ),
            "allow_autonomous_execution": _field(
                "allow_autonomous_execution",
                "Whether approved owner commands may execute autonomously.",
                "boolean",
            ),
        },
        [
            "organization_id",
            "max_steps_per_command",
            "max_project_budget_usd",
            "allow_autonomous_execution",
        ],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "list_owner_commands",
        "List owner commands, their status, approval state, and plan for an organization.",
        {"organization_id": ORG_ID},
        ["organization_id"],
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "get_owner_command_brief",
        "Read the progress, evidence, and decision brief for an owner command.",
        {"organization_id": ORG_ID, "command_id": RUN_ID},
        ["organization_id", "command_id"],
        read_only=True,
        idempotent=True,
    ),
    _tool(
        "create_owner_command",
        "Create a new owner command in awaiting_approval state. This tool never "
        "approves or executes the command.",
        {
            "organization_id": ORG_ID,
            "objective": _field("objective", "What Seldrune should plan and work on."),
        },
        ["organization_id", "objective"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "approve_owner_command",
        "Approve a pending owner command after the owner reviews its plan. "
        "Approval is separate from execution.",
        {"organization_id": ORG_ID, "command_id": RUN_ID},
        ["organization_id", "command_id"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "revoke_owner_command_approval",
        "Revoke approval for a command that has not started execution.",
        {"organization_id": ORG_ID, "command_id": RUN_ID},
        ["organization_id", "command_id"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "execute_owner_command",
        "Execute an already approved owner command. This can trigger configured "
        "external actions and AI spend; it never approves a command.",
        {
            "organization_id": ORG_ID,
            "command_id": RUN_ID,
            "max_steps": _field(
                "max_steps", "Maximum execution steps, bounded by Seldrune governance.", "integer"
            ),
        },
        ["organization_id", "command_id"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "promote_owner_command",
        "Promote an achieved owner command to a project when Seldrune's outcome gates allow it.",
        {"organization_id": ORG_ID, "command_id": RUN_ID},
        ["organization_id", "command_id"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "recover_owner_command",
        "Create a recovery command for an owner command. The new command starts in "
        "awaiting_approval and is not executed.",
        {"organization_id": ORG_ID, "command_id": RUN_ID},
        ["organization_id", "command_id"],
        read_only=False,
        destructive=True,
    ),
    _tool(
        "get_governance_audit_log",
        "Read recent governance audit events for an organization. Sensitive fields "
        "are redacted.",
        {
            "organization_id": ORG_ID,
            "limit": _field("limit", "Number of recent events to return (1-200).", "integer"),
        },
        ["organization_id"],
        read_only=True,
        idempotent=True,
    ),
]


def _deepfacelive_tool(
    name: str,
    description: str,
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
    *,
    read_only: bool,
    idempotent: bool = False,
) -> dict[str, Any]:
    value = _tool(
        name, description, properties, required, read_only=read_only, idempotent=idempotent
    )
    value["securitySchemes"] = [{"type": "oauth2", "scopes": [DEEPFACELIVE_SCOPE]}]
    return value


DEEPFACELIVE_TOOLS = [
    _deepfacelive_tool(
        "pair_deepfacelive_agent",
        "Create a one-time 10-minute code to pair the user's Windows DeepFaceLive computer.",
        read_only=False,
    ),
    _deepfacelive_tool(
        "deepfacelive_status",
        "Read the paired Windows companion heartbeat and whether its "
        "DeepFaceLive process is running.",
        read_only=True,
        idempotent=True,
    ),
    _deepfacelive_tool(
        "deepfacelive_start",
        "Queue a request for the paired companion to launch its configured DeepFaceLive.bat.",
        read_only=False,
        idempotent=True,
    ),
    _deepfacelive_tool(
        "deepfacelive_stop",
        "Queue a request for the paired companion to stop the process tree it launched.",
        read_only=False,
        idempotent=True,
    ),
    _deepfacelive_tool(
        "deepfacelive_command_status",
        "Read the result of a queued DeepFaceLive start or stop request.",
        {"command_id": _field("command_id", "Queued DeepFaceLive command UUID.")},
        ["command_id"],
        read_only=True,
        idempotent=True,
    ),
    _deepfacelive_tool(
        "unpair_deepfacelive_agent",
        "Revoke the paired Windows companion token and expire its queued commands.",
        read_only=False,
        idempotent=True,
    ),
]


def _dispatch_deepfacelive_tool(
    name: str,
    arguments: dict[str, Any],
    user: User,
    session: Session,
) -> Any:
    now = _now()
    agent = session.scalar(
        select(DeepFaceLiveAgent).where(
            DeepFaceLiveAgent.user_id == user.id,
            DeepFaceLiveAgent.revoked_at.is_(None),
        )
    )
    if name == "pair_deepfacelive_agent":
        for old in session.scalars(
            select(DeepFaceLivePairingCode).where(
                DeepFaceLivePairingCode.user_id == user.id,
                DeepFaceLivePairingCode.consumed_at.is_(None),
            )
        ):
            old.consumed_at = now
        code = secrets.token_urlsafe(32)
        session.add(
            DeepFaceLivePairingCode(
                code_sha256=_sha256(code),
                user_id=user.id,
                expires_at=now + timedelta(minutes=10),
            )
        )
        record_audit(
            session,
            actor_user_id=user.id,
            action="deepfacelive.agent_pairing_code_issued",
            resource_type="deepfacelive_agent",
            resource_id=str(user.id),
            details={"expires_in_seconds": 600},
        )
        session.commit()
        return {
            "pairing_code": code,
            "expires_in_seconds": 600,
            "instructions": "Run the Windows companion pair command and paste this code.",
        }

    if name == "deepfacelive_status":
        if agent is None:
            return {"paired": False, "online": False, "app_running": False}
        last_seen = _aware(agent.last_seen_at) if agent.last_seen_at else None
        online = bool(
            last_seen
            and now - last_seen <= timedelta(seconds=90)
            and _aware(agent.token_expires_at) > now
        )
        return {
            "paired": True,
            "online": online,
            "agent_name": agent.agent_name,
            "last_seen_at": last_seen.isoformat() if last_seen else None,
            "app_running": bool(agent.app_running) if online else False,
            "app_pid": agent.app_pid if online and agent.app_running else None,
            "agent_version": agent.agent_version,
        }

    if name == "unpair_deepfacelive_agent":
        if agent is None:
            return {"paired": False}
        agent.revoked_at = now
        for command in session.scalars(
            select(DeepFaceLiveCommand).where(
                DeepFaceLiveCommand.agent_id == agent.id,
                DeepFaceLiveCommand.status.in_(["pending", "claimed"]),
            )
        ):
            command.status = "expired"
            command.completed_at = now
        record_audit(
            session,
            actor_user_id=user.id,
            action="deepfacelive.agent_unpaired",
            resource_type="deepfacelive_agent",
            resource_id=str(agent.id),
            details={},
        )
        session.commit()
        return {"paired": False, "revoked": True}

    if name in {"deepfacelive_start", "deepfacelive_stop"}:
        if agent is None:
            raise ValueError("Pair a Windows DeepFaceLive companion first.")
        last_seen = _aware(agent.last_seen_at) if agent.last_seen_at else None
        if not last_seen or now - last_seen > timedelta(seconds=90):
            raise ValueError("The paired Windows companion is offline.")
        action = "start" if name.endswith("_start") else "stop"
        queued = session.scalar(
            select(DeepFaceLiveCommand)
            .where(
                DeepFaceLiveCommand.agent_id == agent.id,
                DeepFaceLiveCommand.status.in_(["pending", "claimed"]),
                DeepFaceLiveCommand.expires_at > now,
            )
            .order_by(DeepFaceLiveCommand.created_at)
            .limit(1)
        )
        if queued:
            if queued.action != action:
                raise ValueError("A different DeepFaceLive command is still in progress.")
            return {"id": str(queued.id), "action": queued.action, "status": queued.status}
        command = DeepFaceLiveCommand(
            agent_id=agent.id,
            user_id=user.id,
            action=action,
            status="pending",
            expires_at=now + timedelta(seconds=180),
        )
        session.add(command)
        session.flush()
        record_audit(
            session,
            actor_user_id=user.id,
            action=f"deepfacelive.{action}_queued",
            resource_type="deepfacelive_command",
            resource_id=str(command.id),
            details={"action": action},
        )
        session.commit()
        return {"id": str(command.id), "action": action, "status": "pending"}

    if name == "deepfacelive_command_status":
        try:
            command_id = UUID(str(arguments.get("command_id") or ""))
        except ValueError:
            raise ValueError("command_id must be a UUID.") from None
        command = session.scalar(
            select(DeepFaceLiveCommand).where(
                DeepFaceLiveCommand.id == command_id,
                DeepFaceLiveCommand.user_id == user.id,
            )
        )
        if command is None:
            raise ValueError("DeepFaceLive command not found.")
        if command.status in {"pending", "claimed"} and _aware(command.expires_at) <= now:
            command.status = "expired"
            command.completed_at = now
            session.commit()
        return {
            "id": str(command.id),
            "action": command.action,
            "status": command.status,
            "result": command.result,
        }
    raise ValueError(f"Unknown DeepFaceLive tool: {name}")


def _dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    user: User,
    session: Session,
) -> Any:
    if name in {
        "pair_deepfacelive_agent",
        "deepfacelive_status",
        "deepfacelive_start",
        "deepfacelive_stop",
        "deepfacelive_command_status",
        "unpair_deepfacelive_agent",
    }:
        return _dispatch_deepfacelive_tool(name, arguments, user, session)
    if name == "list_owner_organizations":
        rows = session.execute(
            select(Organization, Membership)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user.id,
                Membership.role == Role.OWNER.value,
            )
            .order_by(Organization.name)
        ).all()
        return [
            {"id": str(org.id), "name": org.name, "slug": org.slug, "role": membership.role}
            for org, membership in rows
        ]

    organization_id = str(arguments.get("organization_id") or "")
    membership = _owner_membership(session, user, organization_id)
    org_uuid = UUID(organization_id)

    if name == "get_owner_dashboard":
        return owner_commands.get_owner_dashboard(org_uuid, membership, session)
    if name == "get_governance_policy":
        return owner_commands.get_governance_policy(org_uuid, membership, session)
    if name in {"preview_governance_policy", "update_governance_policy"}:
        payload = owner_commands.GovernancePolicyUpdate.model_validate(
            {
                "max_steps_per_command": arguments.get("max_steps_per_command"),
                "max_project_budget_usd": arguments.get("max_project_budget_usd"),
                "allow_autonomous_execution": arguments.get("allow_autonomous_execution"),
            }
        )
        if name == "preview_governance_policy":
            return owner_commands.preview_governance_policy(org_uuid, payload, membership, session)
        return owner_commands.update_governance_policy(
            org_uuid, payload, membership, user, session
        )
    if name == "list_owner_commands":
        return owner_commands.list_owner_commands(org_uuid, membership, session)
    if name == "get_owner_command_brief":
        run_id = UUID(str(arguments.get("command_id") or ""))
        return owner_commands.get_owner_command_brief(org_uuid, run_id, membership, session)
    if name == "create_owner_command":
        objective = str(arguments.get("objective") or "").strip()
        payload = OrchestrationCreate(objective=objective, context={})
        return owner_commands.create_owner_command(
            org_uuid, payload, membership, user, session
        )

    run_id = UUID(str(arguments.get("command_id") or ""))
    if name == "approve_owner_command":
        return owner_commands.approve_owner_command(
            org_uuid, run_id, membership, user, session
        )
    if name == "revoke_owner_command_approval":
        return owner_commands.revoke_owner_command_approval(
            org_uuid, run_id, membership, user, session
        )
    if name == "execute_owner_command":
        max_steps = int(arguments.get("max_steps", 50))
        payload = AutonomousExecutionRequest(
            max_steps=max_steps,
            stop_on_failure=True,
            max_retries_per_step=0,
        )
        return owner_commands.execute_owner_command(
            org_uuid, run_id, payload, membership, user, session
        )
    if name == "promote_owner_command":
        return owner_commands.promote_owner_command(
            org_uuid, run_id, membership, user, session
        )
    if name == "recover_owner_command":
        return owner_commands.recover_owner_command(
            org_uuid, run_id, membership, user, session
        )
    if name == "get_governance_audit_log":
        limit = int(arguments.get("limit", 50))
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return owner_commands.get_governance_audit_log(
            org_uuid, membership, session, limit=limit
        )
    raise ValueError(f"Unknown tool: {name}")


def _mcp_tool_result(name: str, arguments: Any, user: User, session: Session) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {
            "content": [{"type": "text", "text": "Tool arguments must be an object."}],
            "isError": True,
        }
    try:
        value = _dispatch_tool(name, arguments, user, session)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
        return {"content": [{"type": "text", "text": detail}], "isError": True}
    except (ValidationError, ValueError, TypeError) as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except Exception:
        logger.exception("Seldrune MCP tool call failed: %s", name)
        return {
            "content": [
                {"type": "text", "text": "Seldrune could not complete this tool call."}
            ],
            "isError": True,
        }
    return {"content": [{"type": "text", "text": _json_text(value)}]}


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _handle_message(
    message: Any,
    user: User,
    session: Session,
    *,
    deepfacelive: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _rpc_error(None, -32600, "Invalid Request")
    request_id = message.get("id")
    is_notification = "id" not in message
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return None if is_notification else _rpc_error(request_id, -32600, "Invalid Request")
    method = message["method"]
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return None if is_notification else _rpc_error(request_id, -32602, "Invalid params")
    if is_notification:
        return None
    if method == "initialize":
        requested = str(params.get("protocolVersion") or "2025-03-26")
        protocol_version = requested if requested in SUPPORTED_PROTOCOLS else "2025-11-25"
        return _rpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": (
                        "Seldrune DeepFaceLive Bridge"
                        if deepfacelive
                        else "Seldrune Owner Console"
                    ),
                    "version": settings.app_version,
                },
            },
        )
    if method == "ping":
        return _rpc_result(request_id, {})
    if method == "tools/list":
        return _rpc_result(request_id, {"tools": DEEPFACELIVE_TOOLS if deepfacelive else TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return _rpc_error(request_id, -32602, "Tool name is required")
        tool_list = DEEPFACELIVE_TOOLS if deepfacelive else TOOLS
        if not any(item["name"] == name for item in tool_list):
            return _rpc_error(request_id, -32602, "Unknown tool")
        return _rpc_result(
            request_id,
            _mcp_tool_result(name, params.get("arguments", {}), user, session),
        )
    return _rpc_error(request_id, -32601, "Method not found")


async def _serve_mcp(request: Request, session: Session, *, deepfacelive: bool) -> Response:
    accept = request.headers.get("accept", "application/json")
    if "application/json" not in accept and "text/event-stream" not in accept:
        return Response(status_code=406)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return Response(status_code=415)
    try:
        length = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        length = MAX_REQUEST_BYTES + 1
    if length > MAX_REQUEST_BYTES:
        return Response(status_code=413)
    required_scope = DEEPFACELIVE_SCOPE if deepfacelive else OWNER_SCOPE
    user, _claims = _authenticate_mcp_request(request, session, required_scope=required_scope)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            return Response(status_code=413)
        chunks.append(chunk)
    try:
        message = json.loads(b"".join(chunks))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
    if isinstance(message, list):
        if not message:
            return JSONResponse(_rpc_error(None, -32600, "Invalid Request"), status_code=400)
        replies = [
            reply
            for item in message
            if (
                reply := _handle_message(
                    item, user, session, deepfacelive=deepfacelive
                )
            )
            is not None
        ]
        if not replies:
            return Response(status_code=202)
        return JSONResponse(replies)
    reply = _handle_message(message, user, session, deepfacelive=deepfacelive)
    if reply is None:
        return Response(status_code=202)
    return JSONResponse(reply)


@router.post("/mcp")
async def mcp_endpoint(request: Request, session: SessionDep) -> Response:
    return await _serve_mcp(request, session, deepfacelive=False)


@router.post("/mcp/deepfacelive")
async def deepfacelive_mcp_endpoint(request: Request, session: SessionDep) -> Response:
    return await _serve_mcp(request, session, deepfacelive=True)


@router.get("/mcp")
def mcp_get_not_supported(request: Request, session: SessionDep) -> Response:
    _authenticate_mcp_request(request, session)
    return Response(status_code=405, headers={"Allow": "POST"})


@router.get("/mcp/deepfacelive")
def deepfacelive_mcp_get_not_supported(request: Request, session: SessionDep) -> Response:
    _authenticate_mcp_request(request, session, required_scope=DEEPFACELIVE_SCOPE)
    return Response(status_code=405, headers={"Allow": "POST"})
