"""add agent registry and task engine

Revision ID: 0003_agent_task_engine
Revises: 0002_user_password_hash
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_agent_task_engine"
down_revision = "0002_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("runtime_config", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_agents_organization_slug",
        ),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_agent_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["agents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_organization_id", "tasks", ["organization_id"])
    op.create_index("ix_tasks_assigned_agent_id", "tasks", ["assigned_agent_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_agent_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_agent_id"],
            ["agents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_organization_id", "task_events", ["organization_id"])
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_occurred_at", "task_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_task_events_occurred_at", table_name="task_events")
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_index("ix_task_events_organization_id", table_name="task_events")
    op.drop_table("task_events")

    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_assigned_agent_id", table_name="tasks")
    op.drop_index("ix_tasks_organization_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_agents_organization_id", table_name="agents")
    op.drop_table("agents")
