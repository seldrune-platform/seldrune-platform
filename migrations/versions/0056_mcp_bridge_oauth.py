"""add OAuth storage for the Seldrune Owner Console MCP bridge

Revision ID: 0056_mcp_bridge_oauth
Revises: 0055_live_profile_authorizations
"""

from alembic import op
import sqlalchemy as sa


revision = "0056_mcp_bridge_oauth"
down_revision = "0055_live_profile_authorizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("client_id", sa.String(length=96), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column(
            "token_endpoint_auth_method",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("client_id"),
    )
    op.create_table(
        "mcp_oauth_codes",
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["mcp_oauth_clients.client_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code_sha256"),
    )
    op.create_index("ix_mcp_oauth_codes_expires_at", "mcp_oauth_codes", ["expires_at"])
    op.create_table(
        "mcp_oauth_refresh_tokens",
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=96), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["mcp_oauth_clients.client_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_sha256"),
    )
    op.create_index(
        "ix_mcp_oauth_refresh_tokens_family_id",
        "mcp_oauth_refresh_tokens",
        ["family_id"],
    )
    op.create_index(
        "ix_mcp_oauth_refresh_tokens_user_id",
        "mcp_oauth_refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_mcp_oauth_refresh_tokens_expires_at",
        "mcp_oauth_refresh_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mcp_oauth_refresh_tokens_expires_at",
        table_name="mcp_oauth_refresh_tokens",
    )
    op.drop_index(
        "ix_mcp_oauth_refresh_tokens_user_id",
        table_name="mcp_oauth_refresh_tokens",
    )
    op.drop_index(
        "ix_mcp_oauth_refresh_tokens_family_id",
        table_name="mcp_oauth_refresh_tokens",
    )
    op.drop_table("mcp_oauth_refresh_tokens")
    op.drop_index("ix_mcp_oauth_codes_expires_at", table_name="mcp_oauth_codes")
    op.drop_table("mcp_oauth_codes")
    op.drop_table("mcp_oauth_clients")

