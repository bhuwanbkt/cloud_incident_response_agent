"""create runbook vector tables

Revision ID: 177e78855d8d
Revises: 
Create Date: 2026-09-24 00:03:39.045583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '177e78855d8d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    op.create_table(
        "runbook_documents",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "runbook_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "file_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "file_path",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column(
            "file_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_name"),
    )

    op.create_index(
        "ix_runbook_documents_file_name",
        "runbook_documents",
        ["file_name"],
        unique=True,
    )

    op.create_index(
        "ix_runbook_documents_file_hash",
        "runbook_documents",
        ["file_hash"],
        unique=False,
    )

    op.create_table(
        "runbook_chunks",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "heading",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(384),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["runbook_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name=(
                "uq_runbook_chunks_"
                "document_chunk_index"
            ),
        ),
    )

    op.create_index(
        "ix_runbook_chunks_document_id",
        "runbook_chunks",
        ["document_id"],
        unique=False,
    )

    op.create_index(
        "ix_runbook_chunks_content_hash",
        "runbook_chunks",
        ["content_hash"],
        unique=False,
    )

    op.create_index(
        "ix_runbook_chunks_embedding_hnsw",
        "runbook_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={
            "m": 16,
            "ef_construction": 64,
        },
        postgresql_ops={
            "embedding": "vector_cosine_ops",
        },
    )


def downgrade() -> None:
    op.drop_index(
        "ix_runbook_chunks_embedding_hnsw",
        table_name="runbook_chunks",
    )

    op.drop_index(
        "ix_runbook_chunks_content_hash",
        table_name="runbook_chunks",
    )

    op.drop_index(
        "ix_runbook_chunks_document_id",
        table_name="runbook_chunks",
    )

    op.drop_table("runbook_chunks")

    op.drop_index(
        "ix_runbook_documents_file_hash",
        table_name="runbook_documents",
    )

    op.drop_index(
        "ix_runbook_documents_file_name",
        table_name="runbook_documents",
    )

    op.drop_table("runbook_documents")