"""add owner push subscriptions

Revision ID: 0012_owner_push_subscriptions
Revises: 0011_governance_policies
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_owner_push_subscriptions"
down_revision = "0011_governance_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("expiration_time", sa.Integer(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "endpoint_hash",
            name="uq_owner_push_subscription_endpoint",
        ),
    )
    op.create_index(
        "ix_owner_push_subscriptions_organization_id",
        "owner_push_subscriptions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_owner_push_subscriptions_user_id",
        "owner_push_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_owner_push_subscriptions_endpoint_hash",
        "owner_push_subscriptions",
        ["endpoint_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_owner_push_subscriptions_endpoint_hash",
        table_name="owner_push_subscriptions",
    )
    op.drop_index(
        "ix_owner_push_subscriptions_user_id",
        table_name="owner_push_subscriptions",
    )
    op.drop_index(
        "ix_owner_push_subscriptions_organization_id",
        table_name="owner_push_subscriptions",
    )
    op.drop_table("owner_push_subscriptions")
