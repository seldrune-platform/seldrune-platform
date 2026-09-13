from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.core.research import ConnectorStatus, ResearchStatus
from backend.app.models.membership import Membership
from backend.app.models.research_connector import ResearchConnector
from backend.app.models.research_session import ResearchSession
from backend.app.models.research_source import ResearchSource
from backend.app.schemas.research import (
    ResearchConnectorCreate,
    ResearchConnectorPublic,
    ResearchExecuteRequest,
    ResearchExecutionResponse,
    ResearchSessionCreate,
    ResearchSessionPublic,
    ResearchSourceIngest,
    ResearchSourcePublic,
)
from backend.app.services.audit import record_audit
from backend.app.services.research_engine import (
    ResearchDocument,
    ResearchEngineError,
    execute_research_session,
    ingest_research_document,
)

router = APIRouter(prefix="/organizations", tags=["research"])

research_read_dependency = require_org_permission(Permission.RESEARCH_READ)
research_run_dependency = require_org_permission(Permission.RESEARCH_RUN)
research_manage_dependency = require_org_permission(Permission.RESEARCH_MANAGE)
ResearchReadDep = Annotated[Membership, Depends(research_read_dependency)]
ResearchRunDep = Annotated[Membership, Depends(research_run_dependency)]
ResearchManageDep = Annotated[Membership, Depends(research_manage_dependency)]

_SECRET_MARKERS = ("secret", "password", "token", "api_key", "apikey", "credential")


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in _SECRET_MARKERS):
                return True
            if _contains_secret_key(nested):
                return True
    if isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def _get_session(session: SessionDep, organization_id: UUID, session_id: UUID) -> ResearchSession:
    item = session.scalar(
        select(ResearchSession).where(
            ResearchSession.id == session_id,
            ResearchSession.organization_id == organization_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return item


def _validate_connector_ids(
    session: SessionDep,
    organization_id: UUID,
    connector_ids: list[UUID],
) -> None:
    if not connector_ids:
        return
    found = set(
        session.scalars(
            select(ResearchConnector.id).where(
                ResearchConnector.organization_id == organization_id,
                ResearchConnector.id.in_(connector_ids),
            )
        )
    )
    if found != set(connector_ids):
        raise HTTPException(status_code=404, detail="One or more research connectors not found")


@router.post(
    "/{organization_id}/research/connectors",
    response_model=ResearchConnectorPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_connector(
    organization_id: UUID,
    payload: ResearchConnectorCreate,
    _membership: ResearchManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ResearchConnector:
    if _contains_secret_key(payload.config):
        raise HTTPException(status_code=400, detail="Connector secrets cannot be stored in config")
    existing = session.scalar(
        select(ResearchConnector).where(
            ResearchConnector.organization_id == organization_id,
            ResearchConnector.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Research connector slug already exists")
    connector = ResearchConnector(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        provider=payload.provider.strip().lower(),
        status=ConnectorStatus.ACTIVE.value,
        config_json=payload.config,
        metadata_json=payload.metadata,
    )
    session.add(connector)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="research.connector.created",
        resource_type="research_connector",
        resource_id=str(connector.id),
        details={"provider": connector.provider, "slug": connector.slug},
    )
    session.commit()
    session.refresh(connector)
    return connector


@router.get(
    "/{organization_id}/research/connectors",
    response_model=list[ResearchConnectorPublic],
)
def list_connectors(
    organization_id: UUID,
    _membership: ResearchReadDep,
    session: SessionDep,
) -> list[ResearchConnector]:
    return list(
        session.scalars(
            select(ResearchConnector)
            .where(ResearchConnector.organization_id == organization_id)
            .order_by(ResearchConnector.name)
        )
    )


@router.post(
    "/{organization_id}/research/sessions",
    response_model=ResearchSessionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_research_session(
    organization_id: UUID,
    payload: ResearchSessionCreate,
    _membership: ResearchRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ResearchSession:
    _validate_connector_ids(session, organization_id, payload.connector_ids)
    item = ResearchSession(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        title=payload.title,
        query=payload.query,
        objective=payload.objective,
        status=ResearchStatus.DRAFT.value,
        connector_ids=[str(value) for value in payload.connector_ids],
    )
    session.add(item)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="research.session.created",
        resource_type="research_session",
        resource_id=str(item.id),
        details={"connector_count": len(item.connector_ids)},
    )
    session.commit()
    session.refresh(item)
    return item


@router.get(
    "/{organization_id}/research/sessions",
    response_model=list[ResearchSessionPublic],
)
def list_research_sessions(
    organization_id: UUID,
    _membership: ResearchReadDep,
    session: SessionDep,
) -> list[ResearchSession]:
    return list(
        session.scalars(
            select(ResearchSession)
            .where(ResearchSession.organization_id == organization_id)
            .order_by(ResearchSession.created_at.desc())
        )
    )


@router.post(
    "/{organization_id}/research/sessions/{session_id}/sources",
    response_model=ResearchSourcePublic,
    status_code=status.HTTP_201_CREATED,
)
def ingest_source(
    organization_id: UUID,
    session_id: UUID,
    payload: ResearchSourceIngest,
    _membership: ResearchRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ResearchSource:
    research_session = _get_session(session, organization_id, session_id)
    if payload.connector_id is not None:
        _validate_connector_ids(session, organization_id, [payload.connector_id])
    document = ResearchDocument(
        title=payload.title,
        content=payload.content,
        uri=payload.uri,
        source_type=payload.source_type,
        metadata=payload.metadata,
    )
    return ingest_research_document(
        session,
        research_session=research_session,
        actor_user_id=current_user.id,
        document=document,
        provider=payload.provider.strip().lower(),
        connector_id=payload.connector_id,
    )


@router.post(
    "/{organization_id}/research/sessions/{session_id}/execute",
    response_model=ResearchExecutionResponse,
)
def execute_session(
    organization_id: UUID,
    session_id: UUID,
    payload: ResearchExecuteRequest,
    _membership: ResearchRunDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ResearchExecutionResponse:
    research_session = _get_session(session, organization_id, session_id)
    ids = payload.connector_ids
    if ids is not None:
        _validate_connector_ids(session, organization_id, ids)
    try:
        sources = execute_research_session(
            session,
            research_session=research_session,
            actor_user_id=current_user.id,
            connector_ids=ids,
            max_results_per_connector=payload.max_results_per_connector,
        )
    except ResearchEngineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExecutionResponse(session=research_session, sources=sources)


@router.get(
    "/{organization_id}/research/sessions/{session_id}/sources",
    response_model=list[ResearchSourcePublic],
)
def list_sources(
    organization_id: UUID,
    session_id: UUID,
    _membership: ResearchReadDep,
    session: SessionDep,
) -> list[ResearchSource]:
    _get_session(session, organization_id, session_id)
    return list(
        session.scalars(
            select(ResearchSource)
            .where(
                ResearchSource.organization_id == organization_id,
                ResearchSource.research_session_id == session_id,
            )
            .order_by(ResearchSource.created_at)
        )
    )
