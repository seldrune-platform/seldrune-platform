"""add separate Seldrune GPT conversations

Revision ID: 0057_seldrune_gpt_conversations
Revises: 0056_mcp_bridge_oauth
"""

from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0057_seldrune_gpt_conversations"
down_revision = "0056_mcp_bridge_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seldrune_gpt_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False, server_default="New chat"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_seldrune_gpt_conversations_organization_id",
        "seldrune_gpt_conversations",
        ["organization_id"],
    )
    op.create_index(
        "ix_seldrune_gpt_conversations_user_id",
        "seldrune_gpt_conversations",
        ["user_id"],
    )

    with op.batch_alter_table("seldrune_gpt_messages") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_seldrune_gpt_messages_conversation_id",
            "seldrune_gpt_conversations",
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index(
            "ix_seldrune_gpt_messages_conversation_id",
            ["conversation_id"],
        )

    bind = op.get_bind()
    messages = sa.table(
        "seldrune_gpt_messages",
        sa.column("organization_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("conversation_id", sa.Uuid()),
    )
    conversations = sa.table(
        "seldrune_gpt_conversations",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("title", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    legacy_owners = bind.execute(
        sa.select(messages.c.organization_id, messages.c.user_id)
        .where(messages.c.conversation_id.is_(None))
        .distinct()
    ).all()
    now = datetime.now(timezone.utc)
    for organization_id, user_id in legacy_owners:
        conversation_id = uuid4()
        bind.execute(
            conversations.insert().values(
                id=conversation_id,
                organization_id=organization_id,
                user_id=user_id,
                title="Earlier saved history",
                created_at=now,
                updated_at=now,
            )
        )
        bind.execute(
            messages.update()
            .where(
                messages.c.organization_id == organization_id,
                messages.c.user_id == user_id,
                messages.c.conversation_id.is_(None),
            )
            .values(conversation_id=conversation_id)
        )


def downgrade() -> None:
    with op.batch_alter_table("seldrune_gpt_messages") as batch:
        batch.drop_index("ix_seldrune_gpt_messages_conversation_id")
        batch.drop_constraint(
            "fk_seldrune_gpt_messages_conversation_id",
            type_="foreignkey",
        )
        batch.drop_column("conversation_id")
    op.drop_index(
        "ix_seldrune_gpt_conversations_user_id",
        table_name="seldrune_gpt_conversations",
    )
    op.drop_index(
        "ix_seldrune_gpt_conversations_organization_id",
        table_name="seldrune_gpt_conversations",
    )
    op.drop_table("seldrune_gpt_conversations")
