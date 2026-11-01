"""Smart scheduling entities, inbox, goals, habits and snapshots.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
revision='0006'; down_revision='0005'; branch_labels=None; depends_on=None

def upgrade():
    op.add_column('preferences',sa.Column('energy_peak_start',sa.String(5),nullable=False,server_default='09:00'))
    op.add_column('preferences',sa.Column('energy_peak_end',sa.String(5),nullable=False,server_default='12:00'))
    op.create_table('activity_policies',
      sa.Column('id',sa.Integer(),primary_key=True),sa.Column('activity_id',sa.Integer(),sa.ForeignKey('activities.id',ondelete='CASCADE'),unique=True),
      sa.Column('due_date',sa.Date()),sa.Column('start_date',sa.Date()),sa.Column('end_date',sa.Date()),
      sa.Column('weekdays',sa.JSON()),sa.Column('repeat_every_days',sa.Integer()),sa.Column('preferred_start',sa.String(5)),
      sa.Column('energy',sa.Integer()),sa.Column('prep_minutes',sa.Integer()),sa.Column('travel_minutes',sa.Integer()),
      sa.Column('break_after_minutes',sa.Integer()),sa.Column('depends_on',sa.JSON()),sa.Column('goal_id',sa.Integer()))
    op.create_index('ix_activity_policies_activity_id','activity_policies',['activity_id'],unique=True)
    op.create_table('inbox_tasks',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('title',sa.String(160),nullable=False),
      sa.Column('notes',sa.Text()),sa.Column('due_date',sa.Date()),sa.Column('priority',sa.Integer()),sa.Column('duration_minutes',sa.Integer()),
      sa.Column('state',sa.String(16)),sa.Column('parent_id',sa.Integer()),sa.Column('activity_id',sa.Integer()),
      sa.Column('goal_id',sa.Integer()),sa.Column('created_at',sa.DateTime(timezone=True)))
    op.create_table('goals',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('title',sa.String(160),nullable=False),
      sa.Column('description',sa.Text()),sa.Column('target_minutes_week',sa.Integer()),sa.Column('due_date',sa.Date()),sa.Column('archived',sa.Boolean()))
    op.create_table('habits',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('title',sa.String(160),nullable=False),
      sa.Column('weekdays',sa.JSON()),sa.Column('minutes',sa.Integer()),sa.Column('enabled',sa.Boolean()),sa.Column('linked_activity_id',sa.Integer()))
    op.create_table('habit_checks',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('habit_id',sa.Integer(),sa.ForeignKey('habits.id',ondelete='CASCADE')),
      sa.Column('on_date',sa.Date(),nullable=False),sa.UniqueConstraint('habit_id','on_date',name='uq_habit_date'))
    op.create_index('ix_habit_checks_habit_id','habit_checks',['habit_id'])
    op.create_table('day_templates',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('title',sa.String(100),nullable=False),sa.Column('blocks',sa.JSON(),nullable=False))
    op.create_table('snoozed_reminders',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('on_date',sa.Date(),nullable=False),
      sa.Column('block_id',sa.Integer(),nullable=False),sa.Column('snooze_until',sa.DateTime(timezone=True),nullable=False),
      sa.Column('dismissed',sa.Boolean()),sa.UniqueConstraint('on_date','block_id',name='uq_reminder_day_block'))

def downgrade():
    op.drop_column('preferences','energy_peak_end')
    op.drop_column('preferences','energy_peak_start')
    for t in ('snoozed_reminders','day_templates','habit_checks','habits','goals','inbox_tasks','activity_policies'):
        if t=='habit_checks': op.drop_index('ix_habit_checks_habit_id',table_name=t)
        if t=='activity_policies': op.drop_index('ix_activity_policies_activity_id',table_name=t)
        op.drop_table(t)
