"""chat storage

Revision ID: 20260604_0002
Revises: 20260530_0001
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260604_0002"
down_revision = "20260530_0001"
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
        "chat_sessions",
        *common_columns(),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("external_conversation_id", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_pending_process_id", sa.String(length=36), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "channel",
            "external_conversation_id",
            "owner_id",
            name="uq_chat_sessions_channel_external_owner",
        ),
    )

    op.create_table(
        "chat_messages",
        *common_columns(),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("channel_message_id", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("media_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("pending_process_id", sa.String(length=36), nullable=True),
    )

    op.create_table(
        "chat_pending_process_contexts",
        *common_columns(),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("context_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "conversation_history_refs_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )

    op.create_index("ix_chat_sessions_owner_channel", "chat_sessions", ["owner_id", "channel"])
    op.create_index("ix_chat_sessions_status", "chat_sessions", ["status"])
    op.create_index("ix_chat_sessions_last_message_at", "chat_sessions", ["last_message_at"])
    op.create_index("ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"])
    op.create_index(
        "ix_chat_pending_contexts_session_status",
        "chat_pending_process_contexts",
        ["session_id", "status"],
    )
    op.create_index(
        "ix_chat_pending_contexts_expires_at",
        "chat_pending_process_contexts",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_pending_contexts_expires_at", table_name="chat_pending_process_contexts")
    op.drop_index("ix_chat_pending_contexts_session_status", table_name="chat_pending_process_contexts")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_sessions_last_message_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_status", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_owner_channel", table_name="chat_sessions")
    op.drop_table("chat_pending_process_contexts")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
