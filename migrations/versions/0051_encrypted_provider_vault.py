"""add encrypted provider credential vault

Revision ID: 0051_encrypted_provider_vault
Revises: 0050_tool_credential_reference
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_encrypted_provider_vault"
down_revision = "0050_tool_credential_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "secret_references",
        sa.Column("encrypted_value", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("secret_references", "encrypted_value")
