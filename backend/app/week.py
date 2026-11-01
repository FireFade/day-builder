"""Preview seven days and confirm selected days with optimistic revisions.

Never edits Google events. Confirmation is an explicit POST, not a side effect
of opening the weekly view. All selected revisions are validated before writes.
"""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .plan_preview import preview
from .models import DayPlan, PlanBlock
from .manual_plan import reset_history
from .schemas import WeekApplyIn


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_view(db: Session, day: date):
    monday = monday_for(day)
    result=[]
    for i in range(7):
        current = monday + timedelta(days=i)
        p=preview(db, current)
        result.append({'date':current.isoformat(), 'revision':p['revision'], 'blocks':p['blocks'],
                       'warnings':p['warnings'], 'changes':p['changes'],
                       'needs_update':p['calendar_stale'] or bool(p['changes']),
                       'planned_minutes':sum(b['end_min']-b['start_min'] for b in p['blocks'] if b['kind']!='event'),
                       'meeting_minutes':sum(b['end_min']-b['start_min'] for b in p['blocks'] if b['kind']=='event')})
    return {'monday':monday.isoformat(),'days':result}


def apply_week(db: Session, data: WeekApplyIn):
    monday=monday_for(data.monday)
    if monday != data.monday:
        raise HTTPException(422, 'Вкажіть понеділок вибраного тижня')
    week_dates={monday+timedelta(days=i) for i in range(7)}
    if any(day not in week_dates for day in data.revisions):
        raise HTTPException(422, 'Можна підтвердити лише дні вибраного тижня')
    proposed={}
    for day, revision in data.revisions.items():
        latest=preview(db, day)
        if latest['revision']!=revision:
            raise HTTPException(409, f'{day}: календар або розклад змінився. Перегляньте тиждень повторно.')
        proposed[day]=latest
    try:
        for day,p in proposed.items():
            old=db.query(DayPlan).filter(DayPlan.on_date==day).first()
            reset_history(db,day)
            if old:
                db.delete(old)
                db.flush()
            row=DayPlan(on_date=day,warnings=p['warnings'],calendar_stale=False)
            row.blocks=[PlanBlock(**b) for b in p['blocks']]
            db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'saved_dates':[d.isoformat() for d in sorted(proposed)],'count':len(proposed)}
