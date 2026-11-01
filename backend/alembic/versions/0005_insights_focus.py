"""Focus history and daily reflection.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('focus_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('on_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_focus_sessions_on_date','focus_sessions',['on_date'])
    op.create_table('day_reflections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('on_date', sa.Date(), nullable=False, unique=True),
        sa.Column('mood', sa.Integer(), nullable=False),
        sa.Column('energy', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False))
    op.create_index('ix_day_reflections_on_date','day_reflections',['on_date'])

def downgrade():
    op.drop_index('ix_day_reflections_on_date', table_name='day_reflections')
    op.drop_table('day_reflections')
    op.drop_index('ix_focus_sessions_on_date', table_name='focus_sessions')
    op.drop_table('focus_sessions')
