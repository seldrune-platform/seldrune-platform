"""add durable life execution leases

Revision ID: 0028_life_leases
Revises: 0027_password_recovery
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_life_leases"
down_revision = "0027_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_leases",
        sa.Column("orchestration_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "renewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["orchestration_run_id"],
            ["orchestration_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("orchestration_run_id"),
    )
    op.create_index(
        "ix_life_leases_organization_id",
        "life_leases",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_life_leases_lease_expires_at",
        "life_leases",
        ["lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_life_leases_lease_expires_at", table_name="life_leases")
    op.drop_index("ix_life_leases_organization_id", table_name="life_leases")
    op.drop_table("life_leases")
