from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import SessionDep
from backend.app.models.deepfacelive_bridge import (
    DeepFaceLiveAgent,
    DeepFaceLiveCommand,
    DeepFaceLivePairingCode,
)
from backend.app.models.user import User

router = APIRouter(prefix="/deepfacelive", tags=["deepfacelive-bridge-agent"])
PAIRING_CODE_LIFETIME_SECONDS = 10 * 60
AGENT_TOKEN_LIFETIME_DAYS = 90
COMMAND_LIFETIME_SECONDS = 3 * 60
COMMAND_LEASE_SECONDS = 90


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pairing_code: str = Field(min_length=40, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    agent_name: str = Field(default="DeepFaceLive Windows companion", min_length=1, max_length=120)


class PollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_running: bool
    app_pid: int | None = Field(default=None, ge=1, le=2_147_483_647)
    agent_version: str = Field(default="unknown", max_length=32)


class CommandResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "failed"]
    app_running: bool
    app_pid: int | None = Field(default=None, ge=1, le=2_147_483_647)
    message: str = Field(default="", max_length=300)


def _agent_for_request(request: Request, session: Session) -> DeepFaceLiveAgent:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Agent authentication required")
    agent = session.scalar(
        select(DeepFaceLiveAgent).where(DeepFaceLiveAgent.token_sha256 == _digest(token))
    )
    if (
        agent is None
        or agent.revoked_at is not None
        or _aware(agent.token_expires_at) <= _now()
    ):
        raise HTTPException(status_code=401, detail="Agent authentication required")
    user = session.get(User, agent.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Agent authentication required")
    return agent


@router.post("/agent/pair")
def pair_agent(payload: PairRequest, session: SessionDep) -> dict[str, str | int]:
    code_hash = _digest(payload.pairing_code)
    statement = select(DeepFaceLivePairingCode).where(
        DeepFaceLivePairingCode.code_sha256 == code_hash
    )
    if session.get_bind().dialect.name != "sqlite":
        statement = statement.with_for_update()
    pairing = session.scalar(statement)
    if (
        pairing is None
        or pairing.consumed_at is not None
        or _aware(pairing.expires_at) <= _now()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")

    agent = session.scalar(
        select(DeepFaceLiveAgent).where(DeepFaceLiveAgent.user_id == pairing.user_id)
    )
    raw_token = secrets.token_urlsafe(48)
    expires_at = _now() + timedelta(days=AGENT_TOKEN_LIFETIME_DAYS)
    name = payload.agent_name.strip() or "DeepFaceLive Windows companion"
    if agent is None:
        agent = DeepFaceLiveAgent(
            user_id=pairing.user_id,
            agent_name=name,
            token_sha256=_digest(raw_token),
            token_expires_at=expires_at,
        )
        session.add(agent)
    else:
        agent.agent_name = name
        agent.token_sha256 = _digest(raw_token)
        agent.token_expires_at = expires_at
        agent.last_seen_at = None
        agent.app_running = False
        agent.app_pid = None
        agent.agent_version = "unknown"
        agent.revoked_at = None
    pairing.consumed_at = _now()
    session.commit()
    return {
        "agent_id": str(agent.id),
        "agent_token": raw_token,
        "expires_in_seconds": AGENT_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
    }


@router.post("/agent/commands/next")
def next_command(payload: PollRequest, request: Request, session: SessionDep) -> dict:
    agent = _agent_for_request(request, session)
    now = _now()
    agent.last_seen_at = now
    agent.app_running = payload.app_running
    agent.app_pid = payload.app_pid if payload.app_running else None
    agent.agent_version = payload.agent_version

    statement = (
        select(DeepFaceLiveCommand)
        .where(
            DeepFaceLiveCommand.agent_id == agent.id,
            DeepFaceLiveCommand.expires_at > now,
            or_(
                DeepFaceLiveCommand.status == "pending",
                and_(
                    DeepFaceLiveCommand.status == "claimed",
                    DeepFaceLiveCommand.lease_expires_at <= now,
                ),
            ),
        )
        .order_by(DeepFaceLiveCommand.created_at)
        .limit(1)
    )
    if session.get_bind().dialect.name != "sqlite":
        statement = statement.with_for_update(skip_locked=True)
    command = session.scalar(statement)
    if command is None:
        session.commit()
        return {"command": None}

    command.status = "claimed"
    command.claimed_at = now
    command.lease_expires_at = now + timedelta(seconds=COMMAND_LEASE_SECONDS)
    session.commit()
    return {"command": {"id": str(command.id), "action": command.action}}


@router.post("/agent/commands/{command_id}/result")
def complete_command(
    command_id: UUID,
    payload: CommandResultRequest,
    request: Request,
    session: SessionDep,
) -> dict:
    agent = _agent_for_request(request, session)
    command = session.get(DeepFaceLiveCommand, command_id)
    if command is None or command.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Command not found")
    if command.status != "claimed":
        raise HTTPException(status_code=409, detail="Command is not currently claimed")

    now = _now()
    command.status = payload.status
    command.result = {
        "app_running": payload.app_running,
        "app_pid": payload.app_pid if payload.app_running else None,
        "message": payload.message.strip(),
    }
    command.completed_at = now
    command.lease_expires_at = None
    agent.last_seen_at = now
    agent.app_running = payload.app_running
    agent.app_pid = payload.app_pid if payload.app_running else None
    session.commit()
    return {"id": str(command.id), "status": command.status}
