"""add password hash to users

Revision ID: 0002_user_password_hash
Revises: 0001_core_identity
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_user_password_hash"
down_revision = "0001_core_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "password_hash",
                sa.String(length=255),
                nullable=False,
                server_default="",
            )
        )
        batch_op.alter_column("password_hash", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
