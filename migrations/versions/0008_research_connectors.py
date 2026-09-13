"""add research connector engine

Revision ID: 0008_research_connectors
Revises: 0007_knowledge_memory
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_research_connectors"
down_revision = "0007_knowledge_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_connectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_research_connectors_org_slug",
        ),
    )
    op.create_index(
        "ix_research_connectors_organization_id",
        "research_connectors",
        ["organization_id"],
    )
    op.create_index("ix_research_connectors_provider", "research_connectors", ["provider"])
    op.create_index("ix_research_connectors_status", "research_connectors", ["status"])

    op.create_table(
        "research_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("connector_ids", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_sessions_organization_id",
        "research_sessions",
        ["organization_id"],
    )
    op.create_index("ix_research_sessions_status", "research_sessions", ["status"])

    op.create_table(
        "research_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("research_session_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_entry_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("uri", sa.String(length=1500), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["research_session_id"], ["research_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["research_connectors.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_entry_id"], ["knowledge_entries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "research_session_id",
            "content_sha256",
            name="uq_research_sources_session_hash",
        ),
    )
    op.create_index(
        "ix_research_sources_organization_id",
        "research_sources",
        ["organization_id"],
    )
    op.create_index(
        "ix_research_sources_research_session_id",
        "research_sources",
        ["research_session_id"],
    )
    op.create_index("ix_research_sources_connector_id", "research_sources", ["connector_id"])
    op.create_index(
        "ix_research_sources_knowledge_entry_id",
        "research_sources",
        ["knowledge_entry_id"],
    )
    op.create_index("ix_research_sources_provider", "research_sources", ["provider"])
    op.create_index("ix_research_sources_status", "research_sources", ["status"])
    op.create_index(
        "ix_research_sources_content_sha256",
        "research_sources",
        ["content_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_sources_content_sha256", table_name="research_sources")
    op.drop_index("ix_research_sources_status", table_name="research_sources")
    op.drop_index("ix_research_sources_provider", table_name="research_sources")
    op.drop_index("ix_research_sources_knowledge_entry_id", table_name="research_sources")
    op.drop_index("ix_research_sources_connector_id", table_name="research_sources")
    op.drop_index("ix_research_sources_research_session_id", table_name="research_sources")
    op.drop_index("ix_research_sources_organization_id", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_research_sessions_status", table_name="research_sessions")
    op.drop_index("ix_research_sessions_organization_id", table_name="research_sessions")
    op.drop_table("research_sessions")
    op.drop_index("ix_research_connectors_status", table_name="research_connectors")
    op.drop_index("ix_research_connectors_provider", table_name="research_connectors")
    op.drop_index("ix_research_connectors_organization_id", table_name="research_connectors")
    op.drop_table("research_connectors")
