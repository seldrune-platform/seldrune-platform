from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_RECOVERY_CODE_PATTERN = r"^(?:[0-9A-Fa-f]{4}-){5}[0-9A-Fa-f]{4}$"


class BootstrapStatus(BaseModel):
    required: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)
    organization_slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    @field_validator("organization_slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    recovery_code: str | None = Field(default=None, pattern=_RECOVERY_CODE_PATTERN)

    @model_validator(mode="after")
    def require_at_most_one_mfa_factor(self) -> LoginRequest:
        if self.mfa_code is not None and self.recovery_code is not None:
            raise ValueError("Provide at most one MFA factor")
        return self


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class EmailVerificationResponse(BaseModel):
    verified: bool


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool
    email_verified: bool


class OrganizationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserPublic


class MembershipPublic(BaseModel):
    organization: OrganizationPublic
    role: str
    permissions: list[str]


class MeResponse(BaseModel):
    user: UserPublic
    memberships: list[MembershipPublic]


class MemberPublic(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: str
