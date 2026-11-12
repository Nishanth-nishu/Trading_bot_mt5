"""Foundation tables: system_state, audit_logs.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operating_mode", sa.String(32), nullable=False),
        sa.Column("kill_switch_engaged", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("event", sa.String(96), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_category", "audit_logs", ["category"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_category", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("system_state")
