"""OAuth token vault and imported calendar event keys.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("calendar_events", sa.Column("external_key", sa.String(768), nullable=True))
    op.create_unique_constraint("uq_external_key", "calendar_events", ["external_key"]) if op.get_bind().dialect.name != "sqlite" else None
    if op.get_bind().dialect.name == "sqlite":
        op.create_index("uq_external_key", "calendar_events", ["external_key"], unique=True)
    op.create_table("calendar_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False, unique=True),
        sa.Column("token_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True))
    op.create_table("oauth_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("verifier_ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("oauth_attempts")
    op.drop_table("calendar_connections")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("uq_external_key", table_name="calendar_events")
    else:
        op.drop_constraint("uq_external_key", "calendar_events", type_="unique")
    op.drop_column("calendar_events", "external_key")
