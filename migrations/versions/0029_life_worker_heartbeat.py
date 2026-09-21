"""add durable life worker heartbeat

Revision ID: 0029_life_worker_heartbeat
Revises: 0028_life_leases
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_life_worker_heartbeat"
down_revision = "0028_life_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_worker_heartbeats",
        sa.Column("worker_id", sa.String(length=128), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cycle_count", sa.Integer(), nullable=False),
        sa.Column("commands_advanced", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_life_worker_heartbeats_organization_id",
        "life_worker_heartbeats", ["organization_id"],
    )
    op.create_index(
        "ix_life_worker_heartbeats_last_seen_at",
        "life_worker_heartbeats", ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_life_worker_heartbeats_last_seen_at", table_name="life_worker_heartbeats")
    op.drop_index("ix_life_worker_heartbeats_organization_id", table_name="life_worker_heartbeats")
    op.drop_table("life_worker_heartbeats")
