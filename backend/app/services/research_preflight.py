from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.research import ConnectorStatus
from backend.app.models.research_connector import ResearchConnector
from backend.app.models.research_session import ResearchSession
from backend.app.models.secret_reference import SecretReference
from backend.app.services.secret_vault import SecretVaultError, resolve_secret


def _runtime_reference_issue(session: Session, connector: ResearchConnector) -> str | None:
    if connector.secret_reference_id is None:
        return None
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.id == connector.secret_reference_id,
            SecretReference.organization_id == connector.organization_id,
        )
    )
    if reference is None:
        return "runtime_reference_missing"
    try:
        resolve_secret(reference)
    except SecretVaultError:
        return "runtime_reference_unavailable"
    return None


def _web_issues(connector: ResearchConnector) -> list[str]:
    issues: list[str] = []
    allowed_hosts = {str(value).strip().lower() for value in connector.allowed_hosts if str(value).strip()}
    urls = connector.config_json.get("urls", [])
    if not allowed_hosts:
        issues.append("web_allow_list_missing")
    if not isinstance(urls, list) or not urls:
        issues.append("web_urls_missing")
        return issues
    for raw_url in urls:
        parsed = urlparse(str(raw_url).strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            issues.append("web_url_requires_https")
            continue
        if host not in allowed_hosts:
            issues.append("web_url_outside_allow_list")
    return sorted(set(issues))


def _github_issues(connector: ResearchConnector) -> list[str]:
    issues: list[str] = []
    allowed = {
        str(value).strip().lower()
        for value in connector.allowed_repositories
        if str(value).strip()
    }
    repositories = connector.config_json.get("repositories", [])
    if not allowed:
        issues.append("github_allow_list_missing")
    if not isinstance(repositories, list) or not repositories:
        issues.append("github_repositories_missing")
        return issues
    for raw_repository in repositories:
        repository = str(raw_repository).strip()
        if repository.count("/") != 1:
            issues.append("github_repository_invalid")
            continue
        if repository.lower() not in allowed:
            issues.append("github_repository_outside_allow_list")
    return sorted(set(issues))


def _fixture_issues(connector: ResearchConnector) -> list[str]:
    documents = connector.config_json.get("documents", [])
    if not isinstance(documents, list):
        return ["fixture_documents_invalid"]
    return []


def connector_readiness(
    session: Session,
    connector: ResearchConnector,
    *,
    installed_providers: set[str],
    max_results_per_connector: int,
    allow_approval_required: bool,
) -> dict[str, Any]:
    issues: list[str] = []
    provider = connector.provider.strip().lower()
    approval_required = connector.approval_mode == "always"

    if connector.status != ConnectorStatus.ACTIVE.value:
        issues.append("connector_disabled")
    if provider not in installed_providers:
        issues.append("provider_not_installed")
    if approval_required and not allow_approval_required:
        issues.append("approval_required")
    if connector.max_requests_per_run <= 0:
        issues.append("request_budget_invalid")

    reference_issue = _runtime_reference_issue(session, connector)
    if reference_issue is not None:
        issues.append(reference_issue)

    if provider == "web":
        issues.extend(_web_issues(connector))
    elif provider == "github":
        issues.extend(_github_issues(connector))
    elif provider == "fixture":
        issues.extend(_fixture_issues(connector))

    issues = sorted(set(issues))
    state = "ready"
    if issues:
        state = "approval_required" if issues == ["approval_required"] else "blocked"

    return {
        "connector_id": str(connector.id),
        "name": connector.name,
        "provider": provider,
        "state": state,
        "ready": not issues,
        "approval_required": approval_required,
        "request_budget": min(max_results_per_connector, connector.max_requests_per_run),
        "issues": issues,
    }


def preflight_research_connectors(
    session: Session,
    *,
    research_session: ResearchSession,
    connector_ids: list[UUID] | None,
    installed_providers: set[str],
    max_results_per_connector: int,
    allow_approval_required: bool,
) -> dict[str, Any]:
    selected = connector_ids or [UUID(value) for value in research_session.connector_ids]
    if not selected:
        return {
            "ready": False,
            "connector_count": 0,
            "ready_count": 0,
            "approval_required_count": 0,
            "blocked_count": 0,
            "issues": ["connector_selection_empty"],
            "connectors": [],
        }

    connectors = list(
        session.scalars(
            select(ResearchConnector).where(
                ResearchConnector.organization_id == research_session.organization_id,
                ResearchConnector.id.in_(selected),
            )
        )
    )
    if len(connectors) != len(set(selected)):
        return {
            "ready": False,
            "connector_count": len(set(selected)),
            "ready_count": 0,
            "approval_required_count": 0,
            "blocked_count": len(set(selected)),
            "issues": ["connector_not_found"],
            "connectors": [],
        }

    by_id = {connector.id: connector for connector in connectors}
    checks = [
        connector_readiness(
            session,
            by_id[connector_id],
            installed_providers=installed_providers,
            max_results_per_connector=max_results_per_connector,
            allow_approval_required=allow_approval_required,
        )
        for connector_id in selected
    ]
    ready_count = sum(1 for item in checks if item["state"] == "ready")
    approval_required_count = sum(
        1 for item in checks if item["state"] == "approval_required"
    )
    blocked_count = sum(1 for item in checks if item["state"] == "blocked")
    return {
        "ready": ready_count == len(checks),
        "connector_count": len(checks),
        "ready_count": ready_count,
        "approval_required_count": approval_required_count,
        "blocked_count": blocked_count,
        "issues": [],
        "connectors": checks,
    }


def preflight_failure_message(report: dict[str, Any]) -> str:
    if report.get("issues"):
        return ", ".join(str(value) for value in report["issues"])
    failures: list[str] = []
    for item in report.get("connectors", []):
        if item.get("ready"):
            continue
        issue_text = ",".join(item.get("issues", [])) or "not_ready"
        failures.append(f"{item.get('name', item.get('connector_id'))}: {issue_text}")
    return "; ".join(failures) or "connector_not_ready"
