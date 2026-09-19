"""Aetherion: Seldrune's experimental virtual-compute control plane.

Aetherion is a software abstraction over real compute backends. It does not
claim to create physical/quantum hardware or computation without physical
infrastructure.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum


class ComputeClass(str, Enum):
    RTX_PRO_6000 = "rtx-pro-6000"
    AETHERION_VIRTUAL = "aetherion-virtual"


@dataclass(frozen=True)
class EphemeralJob:
    job_id: str
    compute_class: ComputeClass
    payload_digest: str
    persist_payload: bool = False


@dataclass(frozen=True)
class MonthlyAPIKey:
    token: str
    expires_at: datetime


def issue_monthly_api_key(now: datetime | None = None) -> MonthlyAPIKey:
    now = now or datetime.now(UTC)
    return MonthlyAPIKey(
        token=f"sel_aeth_{secrets.token_urlsafe(32)}",
        expires_at=now + timedelta(days=30),
    )


def build_ephemeral_job(payload: bytes, *, prefer_virtual: bool = True) -> EphemeralJob:
    if not payload:
        raise ValueError("compute payload is required")
    return EphemeralJob(
        job_id=f"aeth-{secrets.token_hex(8)}",
        compute_class=(
            ComputeClass.AETHERION_VIRTUAL
            if prefer_virtual
            else ComputeClass.RTX_PRO_6000
        ),
        payload_digest=hashlib.sha256(payload).hexdigest(),
        persist_payload=False,
    )
