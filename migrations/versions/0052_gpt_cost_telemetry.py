"""add direct GPT cost telemetry

Revision ID: 0052_gpt_cost_telemetry
Revises: 0051_encrypted_provider_vault
"""
from alembic import op
import sqlalchemy as sa

revision = "0052_gpt_cost_telemetry"
down_revision = "0051_encrypted_provider_vault"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column(
            "cached_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
    )
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column("cost_tier", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "seldrune_gpt_messages",
        sa.Column("model_calls", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("seldrune_gpt_messages", "model_calls")
    op.drop_column("seldrune_gpt_messages", "cost_tier")
    op.drop_column("seldrune_gpt_messages", "estimated_cost_usd")
    op.drop_column("seldrune_gpt_messages", "cached_input_tokens")
    op.drop_column("seldrune_gpt_messages", "output_tokens")
    op.drop_column("seldrune_gpt_messages", "input_tokens")
