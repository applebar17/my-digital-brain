"""initial operational tables

Revision ID: 20260530_0001
Revises:
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260530_0001"
down_revision = None
branch_labels = None
depends_on = None


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    ]


def upgrade() -> None:
    op.create_table(
        "telegram_chats",
        *common_columns(),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("chat_id", name="uq_telegram_chats_chat_id"),
    )

    op.create_table(
        "ingestion_sessions",
        *common_columns(),
        sa.Column("telegram_chat_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("pending_question", sa.Text(), nullable=True),
        sa.Column("candidate_graph_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "source_records",
        *common_columns(),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=True),
        sa.Column("transcript_ref", sa.Text(), nullable=True),
        sa.Column("derived_from_source_id", sa.String(length=36), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("channel", "external_id", name="uq_source_records_channel_external_id"),
    )

    op.create_table(
        "provider_request_logs",
        *common_columns(),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=True),
        sa.Column("schema_version", sa.String(length=128), nullable=True),
        sa.Column("privacy_level", sa.String(length=32), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "model_registry",
        *common_columns(),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("capability", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
    )

    op.create_table(
        "prompt_registry",
        *common_columns(),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_prompt_registry_name_version"),
    )

    op.create_table(
        "schema_registry",
        *common_columns(),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_schema_registry_name_version"),
    )

    op.create_table(
        "background_jobs",
        *common_columns(),
        sa.Column("job_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "vector_records",
        *common_columns(),
        sa.Column("vector_store", sa.String(length=64), nullable=False),
        sa.Column("collection", sa.String(length=128), nullable=False),
        sa.Column("vector_id", sa.String(length=255), nullable=False),
        sa.Column("graph_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("vector_store", "collection", "vector_id", name="uq_vector_records_ref"),
    )

    op.create_table(
        "backup_exports",
        *common_columns(),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("export_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "audit_log",
        *common_columns(),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=128), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )

    op.create_index("ix_ingestion_sessions_status", "ingestion_sessions", ["status"])
    op.create_index("ix_source_records_received_at", "source_records", ["received_at"])
    op.create_index("ix_provider_request_logs_provider_model", "provider_request_logs", ["provider", "model"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_index("ix_background_jobs_status", table_name="background_jobs")
    op.drop_index("ix_provider_request_logs_provider_model", table_name="provider_request_logs")
    op.drop_index("ix_source_records_received_at", table_name="source_records")
    op.drop_index("ix_ingestion_sessions_status", table_name="ingestion_sessions")

    op.drop_table("audit_log")
    op.drop_table("backup_exports")
    op.drop_table("vector_records")
    op.drop_table("background_jobs")
    op.drop_table("schema_registry")
    op.drop_table("prompt_registry")
    op.drop_table("model_registry")
    op.drop_table("provider_request_logs")
    op.drop_table("source_records")
    op.drop_table("ingestion_sessions")
    op.drop_table("telegram_chats")
