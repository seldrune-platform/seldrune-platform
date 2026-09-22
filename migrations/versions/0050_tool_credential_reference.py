"""add tool credential reference

Revision ID: 0050_tool_credential_reference
Revises: 0049_cosmic_owner_console
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_tool_credential_reference"
down_revision = "0049_cosmic_owner_console"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_definitions", sa.Column("credential_reference_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_tool_definitions_credential_reference_id"),
        "tool_definitions",
        ["credential_reference_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tool_definitions_credential_reference_id_secret_references",
        "tool_definitions",
        "secret_references",
        ["credential_reference_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tool_definitions_credential_reference_id_secret_references",
        "tool_definitions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_tool_definitions_credential_reference_id"), table_name="tool_definitions")
    op.drop_column("tool_definitions", "credential_reference_id")
