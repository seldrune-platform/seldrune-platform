"""add governance policies

Revision ID: 0011_governance_policies
Revises: 0010_organization_kernel
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_governance_policies"
down_revision = "0010_organization_kernel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "max_steps_per_command",
            sa.Integer(),
            nullable=False,
            server_default="25",
        ),
        sa.Column(
            "max_project_budget_usd",
            sa.Float(),
            nullable=False,
            server_default="100",
        ),
        sa.Column(
            "allow_autonomous_execution",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("governance_policies")
