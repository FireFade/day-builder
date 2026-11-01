"""Manual editable day, persistent undo/redo.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("plan_blocks", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("plan_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("event_signature", sa.String(64), nullable=False),
        sa.Column("undone", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_plan_history_on_date", "plan_history", ["on_date"])

def downgrade():
    op.drop_index("ix_plan_history_on_date", table_name="plan_history")
    op.drop_table("plan_history")
    op.drop_column("plan_blocks", "is_locked")
