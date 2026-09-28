from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


ProfileKind = Literal["face", "voice"]
ProfileGrantStatus = Literal["pending", "approved", "rejected", "revoked", "expired"]
_PROFILE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class ProfileAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_kind: ProfileKind
    profile_id: str = Field(min_length=1, max_length=100, pattern=_PROFILE_ID_PATTERN)
    evidence_reference: str = Field(
        min_length=4,
        max_length=240,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value


class ProfileAuthorizationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    evidence_reviewed: StrictBool = False
    subject_consent_verified: StrictBool = False

    @model_validator(mode="after")
    def require_review_attestations(self) -> "ProfileAuthorizationReview":
        if self.decision == "approve" and not (
            self.evidence_reviewed and self.subject_consent_verified
        ):
            raise ValueError(
                "approval requires reviewed evidence and verified subject consent"
            )
        return self


class ProfileAuthorizationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    profile_kind: ProfileKind
    profile_id: str
    evidence_reference: str
    evidence_sha256: str
    expires_at: datetime
    status: ProfileGrantStatus
    requested_by_user_id: UUID | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    revoked_by_user_id: UUID | None
    revoked_at: datetime | None
    created_at: datetime


class ProfileAuthorizationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    user_id: UUID
    face_profile_id: str = Field(min_length=1, max_length=100, pattern=_PROFILE_ID_PATTERN)
    voice_profile_id: str = Field(min_length=1, max_length=100, pattern=_PROFILE_ID_PATTERN)


class ProfileAuthorizationCheckResult(BaseModel):
    face_profile_authorized: StrictBool
    voice_profile_authorized: StrictBool
