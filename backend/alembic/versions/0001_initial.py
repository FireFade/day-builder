"""Frozen original v0.1 schema.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wake_time", sa.String(5), nullable=False),
        sa.Column("sleep_time", sa.String(5), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("meals", sa.JSON(), nullable=False))
    op.create_table("activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("earliest_start", sa.String(5), nullable=False),
        sa.Column("latest_end", sa.String(5), nullable=False),
        sa.Column("recurrence", sa.String(12), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False))
    op.create_table("calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("end_time", sa.String(5), nullable=False),
        sa.Column("source", sa.String(24), nullable=False))
    op.create_table("day_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False))
    op.create_index("ix_day_plans_on_date", "day_plans", ["on_date"], unique=True)
    op.create_table("plan_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("day_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("start_min", sa.Integer(), nullable=False),
        sa.Column("end_min", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False))
    op.create_index("ix_plan_blocks_plan_id", "plan_blocks", ["plan_id"])


def downgrade():
    op.drop_table("plan_blocks")
    op.drop_table("day_plans")
    op.drop_table("calendar_events")
    op.drop_table("activities")
    op.drop_table("preferences")
