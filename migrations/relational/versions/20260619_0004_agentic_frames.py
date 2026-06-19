"""agentic frames

Revision ID: 20260619_0004
Revises: 20260604_0003
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260619_0004"
down_revision = "20260604_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("active_agentic_frame_id", sa.String(length=36), nullable=True),
    )
    op.create_table(
        "chat_agentic_frames",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("state_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("messages_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("context_payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("compact_trace_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("parent_frame_id", sa.String(length=36), nullable=True),
        sa.Column("parent_tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("active_tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("active_tool_name", sa.String(length=128), nullable=True),
        sa.Column("clarification_packet_json", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_chat_agentic_frames_session_status",
        "chat_agentic_frames",
        ["session_id", "status"],
    )
    op.create_index(
        "ix_chat_agentic_frames_parent",
        "chat_agentic_frames",
        ["parent_frame_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_agentic_frames_parent", table_name="chat_agentic_frames")
    op.drop_index("ix_chat_agentic_frames_session_status", table_name="chat_agentic_frames")
    op.drop_table("chat_agentic_frames")
    op.drop_column("chat_sessions", "active_agentic_frame_id")
