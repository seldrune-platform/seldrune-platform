from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from backend.app.models.task import Task
from backend.app.services.portable_ci_ingestion import ingest_portable_ci_evidence


RAILWAY_GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
DEFAULT_TIMEOUT_SECONDS = 20.0

_DEPLOYMENT_QUERY = """
query deployment($id: String!) {
  deployment(id: $id) {
    id
    status
    meta
  }
}
"""

_DEPLOYMENT_LOGS_QUERY = """
query deploymentLogs($deploymentId: String!, $limit: Int) {
  deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
    timestamp
    message
    severity
  }
}
"""

_RECEIPT_PREFIX = "SELDRUNE_CI_RECEIPT_JSON="
_SIGNATURE_PREFIX = "SELDRUNE_CI_RECEIPT_SIGNATURE="


class RailwayCIProviderError(ValueError):
    pass


class RailwayPortableCIProvider:
    provider_name = "railway"

    def __init__(
        self,
        *,
        token: str,
        token_kind: str = "account",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise RailwayCIProviderError("Railway API token is required")

        normalized_kind = str(token_kind or "").strip().lower()
        if normalized_kind not in {"account", "workspace", "oauth", "project"}:
            raise RailwayCIProviderError(
                "token_kind must be account, workspace, oauth, or project"
            )

        self._token = normalized_token
        self._token_kind = normalized_kind
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token_kind == "project":
            headers["Project-Access-Token"] = self._token
        else:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _query(
        self,
        *,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = httpx.post(
                RAILWAY_GRAPHQL_URL,
                headers=self._headers(),
                json={"query": query, "variables": variables},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RailwayCIProviderError(
                "Railway API request failed"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RailwayCIProviderError(
                "Railway API returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise RailwayCIProviderError("Railway API returned invalid payload")

        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0] if isinstance(errors[0], dict) else {}
            message = str(first.get("message") or "Railway GraphQL query failed")
            raise RailwayCIProviderError(message)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise RailwayCIProviderError("Railway API response has no data")
        return data

    def fetch_execution(self, *, run_id: str) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise RailwayCIProviderError("run_id is required")

        data = self._query(
            query=_DEPLOYMENT_QUERY,
            variables={"id": normalized_run_id},
        )
        deployment = data.get("deployment")
        if not isinstance(deployment, dict):
            raise RailwayCIProviderError("Railway deployment was not found")

        deployment_id = str(deployment.get("id") or "").strip()
        if deployment_id != normalized_run_id:
            raise RailwayCIProviderError(
                "Railway deployment id does not match requested run"
            )

        provider_status = str(deployment.get("status") or "").strip().upper()
        if not provider_status:
            raise RailwayCIProviderError("Railway deployment status is missing")

        meta = deployment.get("meta")
        if not isinstance(meta, dict):
            meta = {}

        commit_sha = str(
            meta.get("commitHash")
            or meta.get("commit_hash")
            or ""
        ).strip()
        if not commit_sha:
            raise RailwayCIProviderError(
                "Railway deployment commit hash is missing"
            )

        if provider_status == "SUCCESS":
            status = "success"
        elif provider_status in {
            "FAILED",
            "CRASHED",
            "REMOVED",
            "SKIPPED",
        }:
            status = "failed"
        else:
            status = provider_status.lower()

        return {
            "provider": self.provider_name,
            "run_id": deployment_id,
            "status": status,
            "commit_sha": commit_sha,
            "provider_status": provider_status,
        }

    def fetch_receipt_bundle(self, *, run_id: str) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise RailwayCIProviderError("run_id is required")

        data = self._query(
            query=_DEPLOYMENT_LOGS_QUERY,
            variables={"deploymentId": normalized_run_id, "limit": 500},
        )
        logs = data.get("deploymentLogs")
        if not isinstance(logs, list):
            raise RailwayCIProviderError("Railway deployment logs are unavailable")

        receipt_text: str | None = None
        signature: str | None = None
        for item in logs:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message") or "").strip()
            if message.startswith(_RECEIPT_PREFIX):
                receipt_text = message[len(_RECEIPT_PREFIX):].strip()
            elif message.startswith(_SIGNATURE_PREFIX):
                signature = message[len(_SIGNATURE_PREFIX):].strip()

        if not receipt_text:
            raise RailwayCIProviderError(
                "Railway deployment did not emit a portable CI receipt"
            )
        if not signature or signature == "unsigned":
            raise RailwayCIProviderError(
                "Railway deployment did not emit a signed portable CI receipt"
            )

        try:
            receipt = json.loads(receipt_text)
        except ValueError as exc:
            raise RailwayCIProviderError(
                "Railway portable CI receipt is invalid JSON"
            ) from exc
        if not isinstance(receipt, dict):
            raise RailwayCIProviderError(
                "Railway portable CI receipt must be an object"
            )

        return {
            "receipt": receipt,
            "signature": signature,
        }


def ingest_railway_portable_ci_evidence(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID | None,
    expected_sha: str,
    deployment_id: str,
    receipt: dict[str, Any],
    signature: str,
    signing_key: str,
    railway_token: str,
    token_kind: str = "account",
) -> dict[str, Any]:
    """Ingest portable CI evidence using Railway-authenticated run metadata."""

    adapter = RailwayPortableCIProvider(
        token=railway_token,
        token_kind=token_kind,
    )
    return ingest_portable_ci_evidence(
        session,
        task=task,
        actor_user_id=actor_user_id,
        expected_sha=expected_sha,
        run_id=deployment_id,
        receipt=receipt,
        signature=signature,
        signing_key=signing_key,
        provider_adapter=adapter,
    )


def ingest_railway_portable_ci_run(
    session: Session,
    *,
    task: Task,
    actor_user_id: UUID | None,
    expected_sha: str,
    deployment_id: str,
    signing_key: str,
    railway_token: str,
    token_kind: str = "account",
) -> dict[str, Any]:
    """Retrieve and ingest a signed receipt from an authenticated Railway run."""

    adapter = RailwayPortableCIProvider(
        token=railway_token,
        token_kind=token_kind,
    )
    bundle = adapter.fetch_receipt_bundle(run_id=deployment_id)
    return ingest_portable_ci_evidence(
        session,
        task=task,
        actor_user_id=actor_user_id,
        expected_sha=expected_sha,
        run_id=deployment_id,
        receipt=bundle["receipt"],
        signature=bundle["signature"],
        signing_key=signing_key,
        provider_adapter=adapter,
    )
