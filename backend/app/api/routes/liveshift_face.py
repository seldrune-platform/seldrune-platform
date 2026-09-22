"""LiveShift external face-transformation API."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from backend.app.api.dependencies import require_org_permission
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.services.face_provider import (
    FaceProviderError,
    FaceSwapRequest,
    ReplicateFaceProvider,
)

router = APIRouter(prefix="/organizations", tags=["liveshift-face"])
face_run_dependency = require_org_permission(Permission.AGENTS_RUN)
FaceRunDep = Annotated[Membership, Depends(face_run_dependency)]


class ExternalFaceTransformRequest(BaseModel):
    target_image: str = Field(min_length=1)
    source_face: str = Field(min_length=1)
    consent_confirmed: bool = False


@router.post("/{organization_id}/liveshift/face/external")
def external_face_transform(
    organization_id: UUID,
    payload: ExternalFaceTransformRequest,
    _membership: FaceRunDep,
) -> dict[str, Any]:
    """Submit one consent-gated image transformation to the configured provider."""
    if not payload.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="consent confirmation is required",
        )

    try:
        provider = ReplicateFaceProvider()
        result = provider.create(
            FaceSwapRequest(
                target_image=payload.target_image,
                source_face=payload.source_face,
                consent_confirmed=True,
            )
        )
    except FaceProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="external face provider request failed",
        ) from exc

    return {
        "provider": "replicate",
        "organization_id": str(organization_id),
        "prediction": result,
    }
