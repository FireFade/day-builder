from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

DEFAULT_MEALS = [
    {"key": "breakfast", "title": "Сніданок", "earliest_start": "08:30", "latest_end": "10:00", "duration_minutes": 30},
    {"key": "lunch", "title": "Обід", "earliest_start": "12:30", "latest_end": "15:00", "duration_minutes": 45},
    {"key": "dinner", "title": "Вечеря", "earliest_start": "18:00", "latest_end": "20:30", "duration_minutes": 45},
]

class Preferences(Base):
    __tablename__ = "preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wake_time: Mapped[str] = mapped_column(String(5), default="08:00")
    sleep_time: Mapped[str] = mapped_column(String(5), default="23:30")
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Kyiv")
    energy_peak_start: Mapped[str] = mapped_column(String(5), default="09:00")
    energy_peak_end: Mapped[str] = mapped_column(String(5), default="12:00")
    meals: Mapped[list] = mapped_column(JSON, default=lambda: [dict(v) for v in DEFAULT_MEALS])

class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="personal")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    earliest_start: Mapped[str] = mapped_column(String(5), default="08:00")
    latest_end: Mapped[str] = mapped_column(String(5), default="23:00")
    recurrence: Mapped[str] = mapped_column(String(12), default="daily")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="manual")
    external_key: Mapped[str | None] = mapped_column(String(768), nullable=True, unique=True)

class CalendarConnection(Base):
    __tablename__ = "calendar_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    token_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="connected")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

class OAuthAttempt(Base):
    __tablename__ = "oauth_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    verifier_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class DayPlan(Base):
    __tablename__ = "day_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    calendar_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocks: Mapped[list["PlanBlock"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="PlanBlock.start_min")

class PlanBlock(Base):
    __tablename__ = "plan_blocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("day_plans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="personal")
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[DayPlan] = relationship(back_populates="blocks")

class PlanHistory(Base):
    __tablename__ = "plan_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    event_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    undone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class FocusSession(Base):
    """Completed focus interval; deliberately independent of ephemeral plan block IDs."""
    __tablename__ = "focus_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="study")
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class DayReflection(Base):
    __tablename__ = "day_reflections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

# v1.0: independent goal/task/recurrence policy records, avoiding destructive changes
# to the existing activity/calendar tables or encrypted OAuth tokens.
class ActivityPolicy(Base):
    __tablename__ = 'activity_policies'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey('activities.id', ondelete='CASCADE'), unique=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    weekdays: Mapped[list] = mapped_column(JSON, default=list)
    repeat_every_days: Mapped[int] = mapped_column(Integer, default=1)
    preferred_start: Mapped[str | None] = mapped_column(String(5))
    energy: Mapped[int] = mapped_column(Integer, default=3)
    prep_minutes: Mapped[int] = mapped_column(Integer, default=0)
    travel_minutes: Mapped[int] = mapped_column(Integer, default=0)
    break_after_minutes: Mapped[int] = mapped_column(Integer, default=0)
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    goal_id: Mapped[int | None] = mapped_column(Integer)

class InboxTask(Base):
    __tablename__ = 'inbox_tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default='')
    due_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    state: Mapped[str] = mapped_column(String(16), default='inbox')
    parent_id: Mapped[int | None] = mapped_column(Integer)
    activity_id: Mapped[int | None] = mapped_column(Integer)
    goal_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class Goal(Base):
    __tablename__ = 'goals'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    target_minutes_week: Mapped[int] = mapped_column(Integer, default=120)
    due_date: Mapped[date | None] = mapped_column(Date)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

class Habit(Base):
    __tablename__ = 'habits'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    weekdays: Mapped[list] = mapped_column(JSON, default=lambda: list(range(7)))
    minutes: Mapped[int] = mapped_column(Integer, default=15)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    linked_activity_id: Mapped[int | None] = mapped_column(Integer)

class HabitCheck(Base):
    __tablename__ = 'habit_checks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey('habits.id', ondelete='CASCADE'), index=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    __table_args__ = (UniqueConstraint('habit_id','on_date', name='uq_habit_date'),)

class DayTemplate(Base):
    __tablename__ = 'day_templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    blocks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

class SnoozedReminder(Base):
    __tablename__ = 'snoozed_reminders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    block_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snooze_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('on_date','block_id', name='uq_reminder_day_block'),)
