from backend.app.db.base import Base
from backend.app.models import AuditLog, Membership, Organization, User  # noqa: F401


def test_core_identity_tables_are_registered() -> None:
    assert {
        "organizations",
        "users",
        "memberships",
        "audit_logs",
    }.issubset(Base.metadata.tables)
