"""track owner push delivery fingerprints

Revision ID: 0013_owner_push_delivery_fingerprint
Revises: 0012_owner_push_subscriptions
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_owner_push_delivery_fingerprint"
down_revision = "0012_owner_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "owner_push_subscriptions",
        sa.Column("last_delivered_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "owner_push_subscriptions",
        sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("owner_push_subscriptions", "last_delivered_at")
    op.drop_column("owner_push_subscriptions", "last_delivered_fingerprint")
