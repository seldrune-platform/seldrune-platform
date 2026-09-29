"""add paired DeepFaceLive companion state and command queue

Revision ID: 0057_deepfacelive_bridge
Revises: 0056_mcp_bridge_oauth
"""

from alembic import op
import sqlalchemy as sa


revision = "0057_deepfacelive_bridge"
down_revision = "0056_mcp_bridge_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deepfacelive_agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("app_running", sa.Boolean(), nullable=False),
        sa.Column("app_pid", sa.Integer(), nullable=True),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_deepfacelive_agents_user_id", "deepfacelive_agents", ["user_id"], unique=True)
    op.create_index(
        "uq_deepfacelive_agents_token_sha256", "deepfacelive_agents", ["token_sha256"], unique=True
    )

    op.create_table(
        "deepfacelive_pairing_codes",
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("code_sha256"),
    )
    op.create_index("ix_deepfacelive_pairing_codes_user_id", "deepfacelive_pairing_codes", ["user_id"])
    op.create_index("ix_deepfacelive_pairing_codes_expires_at", "deepfacelive_pairing_codes", ["expires_at"])

    op.create_table(
        "deepfacelive_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('start', 'stop')", name="ck_deepfacelive_commands_action"),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'completed', 'failed', 'expired')",
            name="ck_deepfacelive_commands_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["deepfacelive_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deepfacelive_commands_agent_status", "deepfacelive_commands", ["agent_id", "status", "created_at"])
    op.create_index("ix_deepfacelive_commands_user_id", "deepfacelive_commands", ["user_id"])
    op.create_index("ix_deepfacelive_commands_status", "deepfacelive_commands", ["status"])
    op.create_index("ix_deepfacelive_commands_expires_at", "deepfacelive_commands", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_deepfacelive_commands_expires_at", table_name="deepfacelive_commands")
    op.drop_index("ix_deepfacelive_commands_status", table_name="deepfacelive_commands")
    op.drop_index("ix_deepfacelive_commands_user_id", table_name="deepfacelive_commands")
    op.drop_index("ix_deepfacelive_commands_agent_status", table_name="deepfacelive_commands")
    op.drop_table("deepfacelive_commands")
    op.drop_index("ix_deepfacelive_pairing_codes_expires_at", table_name="deepfacelive_pairing_codes")
    op.drop_index("ix_deepfacelive_pairing_codes_user_id", table_name="deepfacelive_pairing_codes")
    op.drop_table("deepfacelive_pairing_codes")
    op.drop_index("uq_deepfacelive_agents_token_sha256", table_name="deepfacelive_agents")
    op.drop_index("uq_deepfacelive_agents_user_id", table_name="deepfacelive_agents")
    op.drop_table("deepfacelive_agents")
