"""persist user-facing chat process activity

Revision ID: 20260913_0006
Revises: 20260621_0005
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260913_0006"
down_revision = "20260621_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_process_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("session_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_activity_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_sequence", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_chat_process_states_session_status",
        "chat_process_states",
        ["session_id", "status"],
    )
    op.create_table(
        "chat_activity_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("activity_group", sa.String(length=64), nullable=False),
        sa.Column("activity_key", sa.String(length=128), nullable=False),
        sa.Column("occurrence", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_chat_activity_events_session_sequence",
        ),
    )
    op.create_index(
        "ix_chat_activity_events_session_sequence",
        "chat_activity_events",
        ["session_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_activity_events_session_sequence",
        table_name="chat_activity_events",
    )
    op.drop_table("chat_activity_events")
    op.drop_index(
        "ix_chat_process_states_session_status",
        table_name="chat_process_states",
    )
    op.drop_table("chat_process_states")
