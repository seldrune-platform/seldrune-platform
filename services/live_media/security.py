"""Short-lived session authorization primitives."""
from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class VerifiedClaims:
    user_id: str
    session_id: str
    audience: str
    expires_at: float
    consent_scope: tuple[str, ...]


def authorize(claims: VerifiedClaims, session_id: str, required_scope: str) -> None:
    if claims.expires_at <= time():
        raise PermissionError("session token expired")
    if claims.session_id != session_id:
        raise PermissionError("session mismatch")
    if claims.audience != "seldrune-live-media":
        raise PermissionError("invalid audience")
    if required_scope not in claims.consent_scope:
        raise PermissionError("missing consent scope")
