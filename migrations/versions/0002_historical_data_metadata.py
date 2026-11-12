"""historical_data_metadata

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_data_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("broker_server", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("canonical", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("bar_count", sa.Integer(), nullable=False),
        sa.Column("first_time", sa.DateTime(timezone=True)),
        sa.Column("last_time", sa.DateTime(timezone=True)),
        sa.Column("coverage_months", sa.Float(), nullable=False),
        sa.Column("meets_target", sa.Boolean(), nullable=False),
        sa.Column("meets_minimum", sa.Boolean(), nullable=False),
        sa.Column("quality_status", sa.String(16), nullable=False),
        sa.Column("quality_report", sa.Text(), nullable=False),
        sa.Column("time_basis", sa.String(48), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source", "broker_server", "symbol", "timeframe", name="uq_dataset"),
    )
    op.create_index("ix_historical_data_metadata_symbol", "historical_data_metadata", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_historical_data_metadata_symbol", table_name="historical_data_metadata")
    op.drop_table("historical_data_metadata")
