"""merge the DeepFaceLive and Seldrune GPT conversation migration heads

Revision ID: 0058_merge_deepfacelive_and_gpt_conversations
Revises: 0057_deepfacelive_bridge, 0057_seldrune_gpt_conversations
"""


revision = "0058_merge_deepfacelive_and_gpt_conversations"
down_revision = (
    "0057_deepfacelive_bridge",
    "0057_seldrune_gpt_conversations",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
