"""Track calendar changes that make a saved plan outdated.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("day_plans", sa.Column("calendar_stale", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("day_plans", "calendar_stale")
