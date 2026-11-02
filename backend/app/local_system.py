"""Local backup, reminder snoozing and minimal scheduling diagnostics.

Backups NEVER contain .env, the calendar encryption key or browser state.
Server remains bound to loopback; there is deliberately no public auth here.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import io, json, os, sqlite3, tempfile, zipfile
from contextlib import closing
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import DATABASE_URL, get_db, engine
from .models import DayPlan, PlanBlock, SnoozedReminder

router=APIRouter(prefix='/api', tags=['Local tools'])

@router.get('/backup')
def export_backup():
    if engine.dialect.name != 'sqlite':
        raise HTTPException(501,'Експорт SQLite доступний лише в локальному режимі')
    name=engine.url.database
    if name is None or name==':memory:':raise HTTPException(409,'Експорт тимчасової БД недоступний')
    source_path=Path(name)
    if not source_path.exists():raise HTTPException(404,'Файл бази даних ще не створено')
    # SQLite backup API guarantees a consistent snapshot even while the server is running.
    with tempfile.TemporaryDirectory() as d:
        copied=Path(d)/'daybuilder.db'
        # sqlite3.Connection's context manager commits/rolls back but does not
        # close the connection. Explicitly close both handles before the
        # TemporaryDirectory removes the copied database (required on Windows).
        with closing(sqlite3.connect(str(source_path))) as src:
            with closing(sqlite3.connect(str(copied))) as dst:
                src.backup(dst)
                dst.commit()
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.write(copied,'backend/daybuilder.db')
            z.writestr('BACKUP-README.txt',
                'Day Builder local backup. STOP the server before restoring backend/daybuilder.db.\n'
                'To preserve connected Google Calendar tokens, separately keep .env and backend/.secrets/calendar.key.\n'
                'These secrets are intentionally NOT included. Keep all copies private.\n')
            z.writestr('manifest.json',json.dumps({'format':'daybuilder-sqlite-v1','created_at':datetime.now(timezone.utc).isoformat()}))
    archive.seek(0)
    return StreamingResponse(archive,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="daybuilder-backup.zip"','Cache-Control':'no-store'})

class ReminderSnooze(BaseModel):
    minutes:int=Field(ge=0,le=240)
    dismiss:bool=False

@router.get('/reminders/{on_date}')
def reminders(on_date:date,db:Session=Depends(get_db)):
    plan=db.scalar(select(DayPlan).where(DayPlan.on_date==on_date))
    if not plan:return []
    blocks=db.scalars(select(PlanBlock).where(PlanBlock.plan_id==plan.id,PlanBlock.status=='pending')).all()
    policies={x.block_id:x for x in db.scalars(select(SnoozedReminder).where(SnoozedReminder.on_date==on_date)).all()}
    return [{'block_id':b.id,'title':b.title,'start_min':b.start_min,'status':b.status,
             'dismissed':bool(policies.get(b.id) and policies[b.id].dismissed),
             'snooze_until':((policies[b.id].snooze_until.replace(tzinfo=timezone.utc) if policies[b.id].snooze_until.tzinfo is None else policies[b.id].snooze_until).isoformat() if b.id in policies else None)} for b in blocks]

@router.put('/reminders/{on_date}/{block_id}')
def snooze(on_date:date,block_id:int,data:ReminderSnooze,db:Session=Depends(get_db)):
    block=db.get(PlanBlock,block_id)
    if not block or block.plan.on_date!=on_date:raise HTTPException(404,'Блок розкладу не знайдено')
    row=db.scalar(select(SnoozedReminder).where(SnoozedReminder.on_date==on_date,SnoozedReminder.block_id==block_id))
    if not row:row=SnoozedReminder(on_date=on_date,block_id=block_id);db.add(row)
    row.dismissed=data.dismiss
    row.snooze_until=datetime.now(timezone.utc)+timedelta(minutes=data.minutes)
    db.commit();return {'block_id':block_id,'snooze_until':row.snooze_until.isoformat(),'dismissed':row.dismissed}

@router.get('/planner/diagnostics/{on_date}')
def planner_diagnostics(on_date:date,db:Session=Depends(get_db)):
    from .plan_preview import preview
    p=preview(db,on_date)
    mandatory=[w for w in p['warnings'] if 'Не вдалося' in w or 'Залежність' in w]
    return {'date':str(on_date),'planned_blocks':len(p['blocks']),
            'overloaded':bool(mandatory),'warnings':p['warnings'],
            'required_minutes_unassigned':sum(int(w.split()[3]) for w in p['warnings'] if w.startswith('Не вдалося запланувати ') and ' хв' in w and len(w.split())>3 and w.split()[3].isdigit()),
            'safe_to_apply':not mandatory,'requires_confirmation':True}

@router.post('/plans/blocks/{block_id}/tomorrow')
def defer_to_tomorrow(block_id:int,db:Session=Depends(get_db)):
    """Create a *new*, once-only activity tomorrow; preserve today's audit trail.

    No silent calendar writes or plan replacement. The new day is stale and
    requires preview / explicit application.
    """
    from .models import Activity
    from .manual_plan import as_state, save_edit, check_plan
    block=db.get(PlanBlock,block_id)
    if block is None:raise HTTPException(404,'Блок відсутній')
    if block.kind not in ('activity','custom') or block.status !='pending':
        raise HTTPException(409,'Переносити можна тільки невиконані власні справи')
    today=block.plan.on_date
    check_plan(db,block.plan)
    tomorrow=today+timedelta(days=1)
    old=as_state(block.plan)
    task=Activity(title=block.title,description='Перенесено з '+str(today),category=block.category,
        duration_minutes=block.end_min-block.start_min,priority=3,required=True,
        earliest_start='08:00',latest_end='23:00',recurrence='once',target_date=tomorrow,enabled=True)
    # Don't produce an invalid Activity for a non-15-minute manual block.
    if task.duration_minutes%15!=0:
        raise HTTPException(409,'Перенести можна лише справу з тривалістю, кратною 15 хв. Спершу відредагуйте блок.')
    if block.is_locked:
        raise HTTPException(409,'Спочатку розблокуйте справу')
    block.status='skipped'
    db.add(task)
    other=db.scalar(select(DayPlan).where(DayPlan.on_date==tomorrow))
    if other:other.calendar_stale=True
    save_edit(db,block.plan,old,'Перенесено на завтра: '+block.title)
    db.commit();db.refresh(task)
    return {'activity_id':task.id,'date':tomorrow.isoformat(),'message':'Нова одноразова справа створена. Перебудуйте завтрашній день.'}

@router.get('/events/range')
def events_range(start:date,days:int=42,db:Session=Depends(get_db)):
    """Calendar month/week board; imported events remain read-only."""
    from .models import CalendarEvent
    if days<1 or days>62:raise HTTPException(422,'Період: від 1 до 62 днів')
    last=start+timedelta(days=days-1)
    events=db.scalars(select(CalendarEvent).where(CalendarEvent.on_date>=start,CalendarEvent.on_date<=last)
                      .order_by(CalendarEvent.on_date,CalendarEvent.start_time)).all()
    return [{'id':e.id,'on_date':e.on_date,'title':e.title,'start_time':e.start_time,'end_time':e.end_time,'source':e.source} for e in events]
