"""add seldrune gpt messages

Revision ID: 0030_seldrune_gpt_messages
Revises: 0029_life_worker_heartbeat
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_seldrune_gpt_messages"
down_revision = "0029_life_worker_heartbeat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seldrune_gpt_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("response_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_seldrune_gpt_messages_organization_id",
        "seldrune_gpt_messages",
        ["organization_id"],
    )
    op.create_index("ix_seldrune_gpt_messages_user_id", "seldrune_gpt_messages", ["user_id"])
    op.create_index("ix_seldrune_gpt_messages_created_at", "seldrune_gpt_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_seldrune_gpt_messages_created_at", table_name="seldrune_gpt_messages")
    op.drop_index("ix_seldrune_gpt_messages_user_id", table_name="seldrune_gpt_messages")
    op.drop_index("ix_seldrune_gpt_messages_organization_id", table_name="seldrune_gpt_messages")
    op.drop_table("seldrune_gpt_messages")
