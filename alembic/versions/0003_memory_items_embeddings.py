"""ajoute memory_items et memory_embeddings (RAG)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-11
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="fact"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_items_user_id", "memory_items", ["user_id"])

    op.create_table(
        "memory_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "memory_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memory_items.id"), nullable=False
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
    )

    # Index approximatif (IVFFlat) pour accélérer la recherche par similarité
    # cosinus sur de gros volumes. `lists=100` est un point de départ
    # raisonnable ; à ajuster (règle empirique : sqrt(nombre de lignes))
    # une fois qu'il y a un volume réel de souvenirs en production.
    op.execute(
        "CREATE INDEX ix_memory_embeddings_cosine ON memory_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_embeddings_cosine")
    op.drop_table("memory_embeddings")
    op.drop_index("ix_memory_items_user_id", table_name="memory_items")
    op.drop_table("memory_items")
