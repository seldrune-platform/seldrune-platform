"""add shared Seldrune Mail workspace

Revision ID: 0053_seldrune_mail
Revises: 0052_gpt_cost_telemetry
"""
from alembic import op
import sqlalchemy as sa


revision = "0053_seldrune_mail"
down_revision = "0052_gpt_cost_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("verification_token", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "domain", name="uq_mail_domains_org_domain"),
    )
    op.create_index("ix_mail_domains_organization_id", "mail_domains", ["organization_id"])

    op.create_table(
        "mailboxes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("domain_id", sa.Uuid(), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["domain_id"], ["mail_domains.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email_address", name="uq_mailboxes_org_email"),
    )
    op.create_index("ix_mailboxes_organization_id", "mailboxes", ["organization_id"])
    op.create_index("ix_mailboxes_domain_id", "mailboxes", ["domain_id"])

    op.create_table(
        "mailbox_access",
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=16), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("mailbox_id", "user_id"),
    )

    op.create_table(
        "mail_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mail_drafts_mailbox_id", "mail_drafts", ["mailbox_id"])
    op.create_index("ix_mail_drafts_created_by_user_id", "mail_drafts", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_mail_drafts_created_by_user_id", table_name="mail_drafts")
    op.drop_index("ix_mail_drafts_mailbox_id", table_name="mail_drafts")
    op.drop_table("mail_drafts")
    op.drop_table("mailbox_access")
    op.drop_index("ix_mailboxes_domain_id", table_name="mailboxes")
    op.drop_index("ix_mailboxes_organization_id", table_name="mailboxes")
    op.drop_table("mailboxes")
    op.drop_index("ix_mail_domains_organization_id", table_name="mail_domains")
    op.drop_table("mail_domains")
