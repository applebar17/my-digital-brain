"""vector record foundation

Revision ID: 20260604_0003
Revises: 20260604_0002
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260604_0003"
down_revision = "20260604_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vector_records", sa.Column("embedding_scope", sa.String(length=128), nullable=True))
    op.add_column(
        "vector_records",
        sa.Column("primary_target_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "vector_records",
        sa.Column("primary_target_label", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "vector_records",
        sa.Column("related_target_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "vector_records",
        sa.Column("source_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "vector_records",
        sa.Column(
            "relationship_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column("vector_records", sa.Column("builder_version", sa.String(length=128), nullable=True))
    op.add_column("vector_records", sa.Column("document_checksum", sa.String(length=128), nullable=True))
    op.add_column(
        "vector_records",
        sa.Column(
            "lifecycle_state",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )

    op.create_index(
        "ix_vector_records_primary_target",
        "vector_records",
        ["primary_target_id", "primary_target_label"],
    )
    op.create_index(
        "ix_vector_records_builder_checksum",
        "vector_records",
        ["builder_version", "document_checksum"],
    )
    op.create_index("ix_vector_records_lifecycle", "vector_records", ["lifecycle_state"])


def downgrade() -> None:
    op.drop_index("ix_vector_records_lifecycle", table_name="vector_records")
    op.drop_index("ix_vector_records_builder_checksum", table_name="vector_records")
    op.drop_index("ix_vector_records_primary_target", table_name="vector_records")

    op.drop_column("vector_records", "lifecycle_state")
    op.drop_column("vector_records", "document_checksum")
    op.drop_column("vector_records", "builder_version")
    op.drop_column("vector_records", "relationship_ids_json")
    op.drop_column("vector_records", "source_ids_json")
    op.drop_column("vector_records", "related_target_ids_json")
    op.drop_column("vector_records", "primary_target_label")
    op.drop_column("vector_records", "primary_target_id")
    op.drop_column("vector_records", "embedding_scope")
