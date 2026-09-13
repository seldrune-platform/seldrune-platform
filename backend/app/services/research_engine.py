from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.knowledge import KnowledgeKind
from backend.app.core.research import ConnectorStatus, ResearchSourceStatus, ResearchStatus
from backend.app.models.knowledge import KnowledgeEntry
from backend.app.models.research_connector import ResearchConnector
from backend.app.models.research_session import ResearchSession
from backend.app.models.research_source import ResearchSource
from backend.app.services.audit import record_audit


class ResearchEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchDocument:
    title: str
    content: str
    uri: str | None = None
    source_type: str = "external"
    metadata: dict[str, Any] | None = None


class ResearchAdapter(Protocol):
    def fetch(
        self,
        *,
        query: str,
        config: dict[str, Any],
        limit: int,
    ) -> list[ResearchDocument]: ...


class FixtureResearchAdapter:
    def fetch(
        self,
        *,
        query: str,
        config: dict[str, Any],
        limit: int,
    ) -> list[ResearchDocument]:
        raw_documents = config.get("documents", [])
        if not isinstance(raw_documents, list):
            raise ResearchEngineError("Fixture connector documents must be a list")
        terms = {term.lower() for term in query.split() if len(term) > 1}
        results: list[ResearchDocument] = []
        for raw in raw_documents:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title", "")).strip()
            content = str(raw.get("content", "")).strip()
            if not title or not content:
                continue
            haystack = f"{title} {content}".lower()
            if terms and not any(term in haystack for term in terms):
                continue
            metadata = raw.get("metadata")
            results.append(
                ResearchDocument(
                    title=title,
                    content=content,
                    uri=str(raw["uri"]) if raw.get("uri") else None,
                    source_type=str(raw.get("source_type", "fixture")),
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )
            if len(results) >= limit:
                break
        return results


class ResearchConnectorRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ResearchAdapter] = {
            "fixture": FixtureResearchAdapter(),
        }

    def register(self, provider: str, adapter: ResearchAdapter) -> None:
        key = provider.strip().lower()
        if not key:
            raise ResearchEngineError("Connector provider cannot be empty")
        self._adapters[key] = adapter

    def get(self, provider: str) -> ResearchAdapter:
        adapter = self._adapters.get(provider.strip().lower())
        if adapter is None:
            raise ResearchEngineError(f"Research provider is not installed: {provider}")
        return adapter

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def source_fingerprint(*, provider: str, uri: str | None, title: str, content: str) -> str:
    payload = "\n".join([provider.strip().lower(), uri or "", title.strip(), content.strip()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_existing_source(
    session: Session,
    *,
    research_session_id: UUID,
    content_sha256: str,
) -> ResearchSource | None:
    return session.scalar(
        select(ResearchSource).where(
            ResearchSource.research_session_id == research_session_id,
            ResearchSource.content_sha256 == content_sha256,
        )
    )


def ingest_research_document(
    session: Session,
    *,
    research_session: ResearchSession,
    actor_user_id: UUID,
    document: ResearchDocument,
    provider: str,
    connector_id: UUID | None = None,
) -> ResearchSource:
    fingerprint = source_fingerprint(
        provider=provider,
        uri=document.uri,
        title=document.title,
        content=document.content,
    )
    existing = _get_existing_source(
        session,
        research_session_id=research_session.id,
        content_sha256=fingerprint,
    )
    if existing is not None:
        return existing

    source = ResearchSource(
        organization_id=research_session.organization_id,
        research_session_id=research_session.id,
        connector_id=connector_id,
        created_by_user_id=actor_user_id,
        title=document.title,
        uri=document.uri,
        provider=provider,
        source_type=document.source_type,
        status=ResearchSourceStatus.CAPTURED.value,
        content=document.content,
        content_sha256=fingerprint,
        metadata_json=document.metadata or {},
        retrieved_at=datetime.now(UTC),
    )
    session.add(source)
    session.flush()

    knowledge = KnowledgeEntry(
        organization_id=research_session.organization_id,
        created_by_user_id=actor_user_id,
        title=document.title[:240],
        content=document.content,
        kind=KnowledgeKind.RESEARCH.value,
        tags=["research", provider.lower()],
        source_type=provider.lower(),
        source_uri=document.uri,
        source_label=document.title[:240],
        metadata_json={
            "research_session_id": str(research_session.id),
            "research_source_id": str(source.id),
            "connector_id": str(connector_id) if connector_id else None,
            "content_sha256": fingerprint,
            **(document.metadata or {}),
        },
    )
    session.add(knowledge)
    session.flush()
    source.knowledge_entry_id = knowledge.id
    source.status = ResearchSourceStatus.INGESTED.value
    record_audit(
        session,
        organization_id=research_session.organization_id,
        actor_user_id=actor_user_id,
        action="research.source.ingested",
        resource_type="research_source",
        resource_id=str(source.id),
        details={
            "research_session_id": str(research_session.id),
            "knowledge_entry_id": str(knowledge.id),
            "provider": provider,
        },
    )
    session.commit()
    session.refresh(source)
    return source


def execute_research_session(
    session: Session,
    *,
    research_session: ResearchSession,
    actor_user_id: UUID,
    connector_ids: list[UUID] | None = None,
    max_results_per_connector: int = 10,
    registry: ResearchConnectorRegistry | None = None,
) -> list[ResearchSource]:
    if research_session.status == ResearchStatus.RUNNING.value:
        raise ResearchEngineError("Research session is already running")
    selected = connector_ids or [UUID(value) for value in research_session.connector_ids]
    if not selected:
        raise ResearchEngineError("At least one research connector is required")

    connectors = list(
        session.scalars(
            select(ResearchConnector).where(
                ResearchConnector.organization_id == research_session.organization_id,
                ResearchConnector.id.in_(selected),
            )
        )
    )
    if len(connectors) != len(set(selected)):
        raise ResearchEngineError("One or more research connectors were not found")

    research_session.status = ResearchStatus.RUNNING.value
    research_session.started_at = datetime.now(UTC)
    research_session.completed_at = None
    session.commit()
    connector_registry = registry or ResearchConnectorRegistry()
    captured: list[ResearchSource] = []
    failures: list[dict[str, str]] = []

    for connector in connectors:
        if connector.status != ConnectorStatus.ACTIVE.value:
            failures.append({"connector_id": str(connector.id), "error": "connector disabled"})
            continue
        try:
            adapter = connector_registry.get(connector.provider)
            documents = adapter.fetch(
                query=research_session.query,
                config=connector.config_json,
                limit=max_results_per_connector,
            )
            for document in documents:
                captured.append(
                    ingest_research_document(
                        session,
                        research_session=research_session,
                        actor_user_id=actor_user_id,
                        document=document,
                        provider=connector.provider,
                        connector_id=connector.id,
                    )
                )
        except ResearchEngineError as exc:
            failures.append({"connector_id": str(connector.id), "error": str(exc)})

    research_session.completed_at = datetime.now(UTC)
    research_session.status = (
        ResearchStatus.COMPLETED.value if captured or not failures else ResearchStatus.FAILED.value
    )
    research_session.summary = {
        "source_count": len(captured),
        "connector_count": len(connectors),
        "failure_count": len(failures),
        "failures": failures,
    }
    record_audit(
        session,
        organization_id=research_session.organization_id,
        actor_user_id=actor_user_id,
        action="research.session.completed",
        resource_type="research_session",
        resource_id=str(research_session.id),
        details=research_session.summary,
    )
    session.commit()
    session.refresh(research_session)
    return captured
