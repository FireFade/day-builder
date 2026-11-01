"""Aggregated only from saved plans; no inferred productivity claims.

Dates without a saved plan are not treated as failed days.
"""
from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session
from .models import DayPlan, FocusSession, DayReflection


def get_insights(db: Session, end_date: date, days: int = 7):
    start_date = end_date - timedelta(days=days - 1)
    plans = db.scalars(select(DayPlan).where(DayPlan.on_date.between(start_date, end_date)).options(selectinload(DayPlan.blocks)).order_by(DayPlan.on_date)).all()
    focus = db.scalars(select(FocusSession).where(FocusSession.on_date.between(start_date, end_date))).all()
    reflections = db.scalars(select(DayReflection).where(DayReflection.on_date.between(start_date, end_date))).all()
    totals = dict(done=0, skipped=0, pending=0, activity_minutes=0, meeting_minutes=0,
                  meal_minutes=0, focus_minutes=sum(f.minutes for f in focus))
    by_category = defaultdict(int)
    daily = []
    plan_map = {p.on_date: p for p in plans}
    reflection_map = {r.on_date:r for r in reflections}
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        plan = plan_map.get(day)
        day_done = day_pending = day_skipped = day_minutes = 0
        if plan:
            for block in plan.blocks:
                length = block.end_min - block.start_min
                if block.kind == 'activity':
                    totals[block.status] += 1
                    totals['activity_minutes'] += length
                    by_category[block.category] += length
                    day_minutes += length
                    if block.status == 'done': day_done += 1
                    elif block.status == 'skipped': day_skipped += 1
                    else: day_pending += 1
                elif block.kind == 'custom':
                    # Custom blocks may be marked done but do not inflate activity count.
                    by_category[block.category] += length
                elif block.kind == 'event': totals['meeting_minutes'] += length
                elif block.kind == 'meal': totals['meal_minutes'] += length
        reflection = reflection_map.get(day)
        daily.append({'date':day.isoformat(), 'has_plan':bool(plan), 'stale': bool(plan and plan.calendar_stale),
                      'done':day_done, 'pending':day_pending, 'skipped':day_skipped,
                      'activity_minutes':day_minutes,
                      'focus_minutes':sum(f.minutes for f in focus if f.on_date == day),
                      'mood':reflection.mood if reflection else None,
                      'energy':reflection.energy if reflection else None})
    count = totals['done'] + totals['skipped'] + totals['pending']
    return {'start_date':start_date.isoformat(), 'end_date':end_date.isoformat(), 'days':days,
            'planned_days':len(plans), 'totals':{**totals, 'completion_percent':round(totals['done']/count*100) if count else None},
            'category_minutes':dict(sorted(by_category.items())), 'daily':daily,
            'recorded_reflections':len(reflections), 'recorded_focus_sessions':len(focus)}
