"""drop legacy pending process chat storage

Revision ID: 20260621_0005
Revises: 20260619_0004
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260621_0005"
down_revision = "20260619_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chat_pending_process_contexts" in tables:
        op.drop_index("ix_chat_pending_contexts_expires_at", table_name="chat_pending_process_contexts")
        op.drop_index("ix_chat_pending_contexts_session_status", table_name="chat_pending_process_contexts")
        op.drop_table("chat_pending_process_contexts")
    chat_session_columns = {column["name"] for column in inspector.get_columns("chat_sessions")} if "chat_sessions" in tables else set()
    if "active_pending_process_id" in chat_session_columns:
        op.drop_column("chat_sessions", "active_pending_process_id")
    chat_message_columns = {column["name"] for column in inspector.get_columns("chat_messages")} if "chat_messages" in tables else set()
    if "pending_process_id" in chat_message_columns:
        op.drop_column("chat_messages", "pending_process_id")


def downgrade() -> None:
    op.add_column("chat_messages", sa.Column("pending_process_id", sa.String(length=36), nullable=True))
    op.add_column("chat_sessions", sa.Column("active_pending_process_id", sa.String(length=36), nullable=True))
    op.create_table(
        "chat_pending_process_contexts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_metadata_json", sa.JSON(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("conversation_history_refs_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
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
