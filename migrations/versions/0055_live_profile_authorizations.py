"""add reviewed LiveShell profile authorization registry

Revision ID: 0055_live_profile_authorizations
Revises: 0054_zoho_mail_connection
"""
from alembic import op
import sqlalchemy as sa


revision = "0055_live_profile_authorizations"
down_revision = "0054_zoho_mail_connection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_profile_authorizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_kind", sa.String(length=16), nullable=False),
        sa.Column("profile_id", sa.String(length=100), nullable=False),
        sa.Column("evidence_reference", sa.String(length=240), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "profile_kind IN ('face', 'voice')",
            name="ck_live_profile_authorizations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked', 'expired')",
            name="ck_live_profile_authorizations_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_profile_authorizations_organization_id",
        "live_profile_authorizations",
        ["organization_id"],
    )
    op.create_index(
        "ix_live_profile_authorizations_user_id",
        "live_profile_authorizations",
        ["user_id"],
    )
    op.create_index(
        "ix_live_profile_authorizations_expires_at",
        "live_profile_authorizations",
        ["expires_at"],
    )
    op.create_index(
        "ix_live_profile_authorizations_status",
        "live_profile_authorizations",
        ["status"],
    )
    op.create_index(
        "ix_live_profile_authorizations_org_user",
        "live_profile_authorizations",
        ["organization_id", "user_id"],
    )
    op.create_index(
        "uq_live_profile_authorizations_active",
        "live_profile_authorizations",
        ["organization_id", "user_id", "profile_kind", "profile_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'approved')"),
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_live_profile_authorizations_active",
        table_name="live_profile_authorizations",
    )
    op.drop_index(
        "ix_live_profile_authorizations_org_user",
        table_name="live_profile_authorizations",
    )
    op.drop_index(
        "ix_live_profile_authorizations_status",
        table_name="live_profile_authorizations",
    )
    op.drop_index(
        "ix_live_profile_authorizations_expires_at",
        table_name="live_profile_authorizations",
    )
    op.drop_index(
        "ix_live_profile_authorizations_user_id",
        table_name="live_profile_authorizations",
    )
    op.drop_index(
        "ix_live_profile_authorizations_organization_id",
        table_name="live_profile_authorizations",
    )
    op.drop_table("live_profile_authorizations")
