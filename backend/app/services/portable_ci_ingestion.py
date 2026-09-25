from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.task import Task, TaskEvent
from backend.app.services.audit import record_audit
from backend.app.services.external_actions import portable_ci_verify_receipt
from backend.app.services.portable_ci_evidence import (
    PortableCIEvidenceError,
    validate_portable_ci_evidence,
)
from backend.app.services.tool_gateway import ToolGatewayError


class AuthenticatedPortableCIProvider(Protocol):
    provider_name: str

    def fetch_execution(self, *, run_id: str) -> dict[str, Any]:
        """Return execution metadata fetched through an authenticated adapter."""


class PortableCIIngestionError(ValueError):
    pass


def _normalized_text(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise PortableCIIngestionError(f"{field} is required")
    return normalized


def ingest_portable_ci_evidence(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID | None,
    expected_sha: str,
    run_id: str,
    receipt: dict[str, Any],
    signature: str,
    signing_key: str,
    provider_adapter: AuthenticatedPortableCIProvider,
) -> dict[str, Any]:
    """Attach portable CI evidence only after both trust layers validate.

    Provider execution metadata is fetched by an internal authenticated adapter.
    The caller cannot supply a free-form provider execution object.

    The repository-owned CI receipt must also pass HMAC verification. Successful
    ingestion stores the signed receipt on the task so the compiled-contract
    fallback can independently re-verify it before a governed merge.
    """

    normalized_sha = _normalized_text(expected_sha, field="expected_sha").lower()
    normalized_run_id = _normalized_text(run_id, field="run_id")
    normalized_signature = _normalized_text(signature, field="signature")
    normalized_provider = _normalized_text(
        getattr(provider_adapter, "provider_name", None),
        field="provider_name",
    ).lower()

    raw_execution = provider_adapter.fetch_execution(run_id=normalized_run_id)
    if not isinstance(raw_execution, dict):
        raise PortableCIIngestionError(
            "authenticated provider adapter returned invalid execution metadata"
        )

    reported_provider = str(raw_execution.get("provider") or "").strip().lower()
    if reported_provider and reported_provider != normalized_provider:
        raise PortableCIIngestionError(
            "provider execution identity does not match authenticated adapter"
        )

    execution = {
        **raw_execution,
        "authenticated": True,
        "provider": normalized_provider,
        "run_id": normalized_run_id,
    }

    try:
        signed = portable_ci_verify_receipt(
            {
                "receipt": receipt,
                "signature": normalized_signature,
            },
            signing_key,
        )
    except ToolGatewayError as exc:
        raise PortableCIIngestionError(str(exc)) from exc

    signed_sha = str(signed.get("head_sha") or "").strip().lower()
    if signed_sha != normalized_sha:
        raise PortableCIIngestionError(
            "signed portable CI receipt does not match expected_sha"
        )

    try:
        provider_verified = validate_portable_ci_evidence(
            expected_sha=normalized_sha,
            provider_execution=execution,
            receipt=receipt,
        )
    except PortableCIEvidenceError as exc:
        raise PortableCIIngestionError(str(exc)) from exc

    provider_commit = str(provider_verified.get("commit_sha") or "").strip().lower()
    if provider_commit != signed_sha:
        raise PortableCIIngestionError(
            "provider execution and signed receipt commit do not match"
        )

    input_data = dict(task.input_data or {})
    input_data["portable_ci_evidence"] = {
        "receipt": receipt,
        "signature": normalized_signature,
        "provider": {
            "name": provider_verified["provider"],
            "run_id": provider_verified["run_id"],
            "commit_sha": provider_verified["commit_sha"],
            "receipt_id": provider_verified["evidence"]["receipt_id"],
        },
        "signed_receipt": {
            "receipt_id": signed["evidence"]["receipt_id"],
            "receipt_digest": signed["receipt_digest"],
            "signature_verified": True,
        },
    }
    task.input_data = input_data

    event_details = {
        "provider": provider_verified["provider"],
        "run_id": provider_verified["run_id"],
        "commit_sha": provider_verified["commit_sha"],
        "provider_receipt_id": provider_verified["evidence"]["receipt_id"],
        "signed_receipt_id": signed["evidence"]["receipt_id"],
        "receipt_digest": signed["receipt_digest"],
    }
    session.add(task)
    session.add(
        TaskEvent(
            organization_id=task.organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            event_type="portable_ci.evidence_ingested",
            details=event_details,
        )
    )
    record_audit(
        session,
        organization_id=task.organization_id,
        actor_user_id=actor_user_id,
        action="portable_ci.evidence_ingested",
        resource_type="task",
        resource_id=str(task.id),
        details=event_details,
    )
    session.commit()
    session.refresh(task)

    return {
        "verified": True,
        "provider": provider_verified["provider"],
        "run_id": provider_verified["run_id"],
        "commit_sha": provider_verified["commit_sha"],
        "provider_receipt_id": provider_verified["evidence"]["receipt_id"],
        "signed_receipt_id": signed["evidence"]["receipt_id"],
        "receipt_digest": signed["receipt_digest"],
    }
