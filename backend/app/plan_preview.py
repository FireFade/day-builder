"""Non-mutating plan preview and optimistic confirmation for a local planner.

The fingerprint covers all inputs relevant to a plan and the prior plan state.
If any calendar event, preference, activity, or completion changes between
preview and apply, the client must request a new preview.
"""
import hashlib
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Activity, ActivityPolicy, CalendarEvent, DayPlan, Preferences
from .planner import generate


def snapshot(db: Session, day: date):
    settings = db.get(Preferences, 1)
    if settings is None:
        from .models import DEFAULT_MEALS
        settings = Preferences(id=1, wake_time="08:00", sleep_time="23:30", timezone="Europe/Kyiv", meals=[dict(m) for m in DEFAULT_MEALS])
        # Deliberately not added to session: preview does not write to DB.
    activities = db.scalars(select(Activity).order_by(Activity.id)).all()
    policies={p.activity_id:p for p in db.scalars(select(ActivityPolicy)).all()}
    events = db.scalars(select(CalendarEvent).where(CalendarEvent.on_date == day).order_by(CalendarEvent.id)).all()
    previous = db.scalar(select(DayPlan).where(DayPlan.on_date == day).options(selectinload(DayPlan.blocks)))
    completed = [b for b in previous.blocks if b.status == 'done' and b.kind == 'activity'] if previous else []
    preserved = [b for b in previous.blocks if b not in completed and
                 ((b.is_locked and b.kind in ('activity', 'meal', 'custom')) or b.kind == 'custom')
                 and b.status != 'skipped'] if previous else []
    skipped = [b.source_id for b in previous.blocks if b.kind == 'activity' and b.status == 'skipped'] if previous else []
    # Include all previous blocks: a status change should invalidate a preview.
    signature = {
        'date': str(day),
        'settings': {
            'wake_time': settings.wake_time, 'sleep_time': settings.sleep_time,
            'timezone': settings.timezone, 'meals': settings.meals,
            'energy_peak_start': settings.energy_peak_start, 'energy_peak_end': settings.energy_peak_end,
        },
        'activities': [{k: getattr(a, k) for k in (
            'id', 'title', 'description', 'category', 'duration_minutes', 'priority',
            'required', 'earliest_start', 'latest_end', 'recurrence', 'target_date', 'enabled')}
            for a in activities],
        'policies': [{k:getattr(p,k) for k in ('activity_id','due_date','start_date','end_date',
                     'weekdays','repeat_every_days','preferred_start','energy','prep_minutes','travel_minutes',
                     'break_after_minutes','depends_on','goal_id')} for p in sorted(policies.values(),key=lambda p:p.activity_id)],
        'events': [{k: getattr(e, k) for k in (
            'id', 'source', 'external_key', 'title', 'start_time', 'end_time')}
            for e in events],
        'previous': None if previous is None else {
            'id': previous.id, 'generated_at': previous.generated_at,
            'calendar_stale': previous.calendar_stale,
            'blocks': [{k: getattr(b, k) for k in (
                'id', 'kind', 'source_id', 'title', 'category', 'start_min', 'end_min', 'status', 'is_locked')}
                for b in previous.blocks],
        },
    }
    data = json.dumps(signature, default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    revision = hashlib.sha256(data.encode('utf-8')).hexdigest()
    return settings, activities, events, previous, completed, preserved, skipped, revision, policies


def preview(db: Session, day: date):
    settings, activities, events, previous, completed, preserved, skipped, revision, policies = snapshot(db, day)
    blocks, warnings = generate(day, settings, activities, events, completed, preserved, skipped, policies)
    old = {(b.kind, b.source_id, b.title): (b.start_min, b.end_min)
           for b in previous.blocks} if previous else {}
    new = {(b['kind'], b['source_id'], b['title']): (b['start_min'], b['end_min'])
           for b in blocks}
    # Human-readable changes for tasks only; calendar events are external fixed inputs.
    changes = []
    for k in sorted(set(old) | set(new), key=lambda x: (str(x[0]), str(x[1]), str(x[2]))):
        if k[0] == 'event' or old.get(k) == new.get(k):
            continue
        kind = 'added' if k not in old else 'removed' if k not in new else 'moved'
        changes.append({'title': k[2], 'kind': kind, 'before': old.get(k), 'after': new.get(k)})
    return {
        'on_date': day, 'revision': revision,
        'calendar_stale': bool(previous and previous.calendar_stale),
        'blocks': blocks, 'warnings': warnings, 'changes': changes,
        'unscheduled_required': sum('обов’язков' in w for w in warnings),
    }
