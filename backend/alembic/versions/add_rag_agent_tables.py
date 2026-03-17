"""Add RAG and Agent memory tables

Revision ID: add_rag_agent_tables
Revises: add_template_is_public
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_rag_agent_tables'
down_revision = 'add_template_is_public'
branch_labels = None
depends_on = None


def upgrade():
    # Create knowledge_embeddings table
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text),
        sa.Column("embedding_model", sa.String(100)),
        sa.Column("token_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_embeddings_document", "knowledge_embeddings", ["document_id"])
    op.create_index("ix_knowledge_embeddings_chunk", "knowledge_embeddings", ["document_id", "chunk_index"])

    # Create check_item_regulations table
    op.create_table(
        "check_item_regulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("template_items.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "knowledge_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("relevance_score", sa.Float, server_default="0.0"),
        sa.Column("relevant_section", sa.Text),
        sa.Column("is_auto_linked", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_check_item_regulations_item", "check_item_regulations", ["template_item_id"])
    op.create_index("ix_check_item_regulations_doc", "check_item_regulations", ["knowledge_document_id"])

    # Create agent_memories table
    op.create_table(
        "agent_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text),
        sa.Column("importance_score", sa.Float, server_default="0.5"),
        sa.Column("access_count", sa.Integer, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("extra_data", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_memories_user", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_session", "agent_memories", ["session_id"])
    op.create_index("ix_agent_memories_type", "agent_memories", ["memory_type"])

    # Create template_recommendations table
    op.create_table(
        "template_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "enterprise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("enterprises.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_templates.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column("recommendation_score", sa.Float),
        sa.Column("recommendation_reasons", sa.Text),
        sa.Column("was_accepted", sa.Boolean),
        sa.Column("was_effective", sa.Boolean),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_template_recommendations_enterprise", "template_recommendations", ["enterprise_id"])
    op.create_index("ix_template_recommendations_template", "template_recommendations", ["template_id"])

    # Create photo_analyses table
    op.create_table(
        "photo_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "media_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_files.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "task_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_item_records.id", ondelete="SET NULL")
        ),
        sa.Column("analysis_type", sa.String(50), server_default="compliance"),
        sa.Column("detected_issues", sa.Text),
        sa.Column("compliance_status", sa.String(20)),
        sa.Column("confidence_score", sa.Float),
        sa.Column("analysis_result", sa.Text),
        sa.Column("recommendations", sa.Text),
        sa.Column("model_used", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_photo_analyses_media", "photo_analyses", ["media_file_id"])
    op.create_index("ix_photo_analyses_task_item", "photo_analyses", ["task_item_id"])


def downgrade():
    op.drop_table("photo_analyses")
    op.drop_table("template_recommendations")
    op.drop_table("agent_memories")
    op.drop_table("check_item_regulations")
    op.drop_table("knowledge_embeddings")