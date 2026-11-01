"""Local manual timetable editor: validates constraints, stores history and supports undo/redo.

No endpoint changes external calendar events. All edits are transactional and saved
in SQLite/PostgreSQL, not browser-only state.
"""
import hashlib
import json
from datetime import date
from sqlalchemy import select, delete
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException
from .models import CalendarEvent, DayPlan, PlanBlock, PlanHistory, Preferences
from .schemas import BlockEditIn, CustomBlockIn
from .planner import conflict
from .schemas import minutes

EDITABLE = ('activity', 'meal', 'custom')
FIELDS = ('kind', 'source_id', 'title', 'category', 'start_min', 'end_min', 'status', 'explanation', 'is_locked')

def get_plan(db: Session, day: date) -> DayPlan:
    plan = db.scalar(select(DayPlan).where(DayPlan.on_date == day).options(selectinload(DayPlan.blocks)))
    if plan is None:
        raise HTTPException(404, 'Спочатку побудуйте розклад цього дня')
    return plan

def calendar_hash(db: Session, day: date) -> str:
    events = db.scalars(select(CalendarEvent).where(CalendarEvent.on_date == day).order_by(CalendarEvent.id)).all()
    content = [(e.id, e.title, e.start_time, e.end_time, e.source) for e in events]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()

def check_plan(db: Session, plan: DayPlan):
    if plan.calendar_stale:
        raise HTTPException(409, 'Google Calendar змінився. Спочатку перебудуйте день.')
    actual = db.scalars(select(CalendarEvent).where(CalendarEvent.on_date == plan.on_date)).all()
    planned = sorted((b.source_id, b.title, b.start_min, b.end_min) for b in plan.blocks if b.kind == 'event')
    incoming = sorted((e.id, e.title, minutes(e.start_time), minutes(e.end_time)) for e in actual)
    if planned != incoming:
        raise HTTPException(409, 'Календарні події змінилися. Спочатку перебудуйте день.')

def as_state(plan: DayPlan) -> dict:
    return {'warnings': list(plan.warnings), 'calendar_stale': bool(plan.calendar_stale),
            'blocks': [{key: getattr(b, key) for key in FIELDS} for b in plan.blocks]}

def restore(db: Session, plan: DayPlan, state: dict):
    plan.blocks.clear()
    db.flush()
    plan.warnings = state['warnings']
    plan.calendar_stale = state['calendar_stale']
    for data in state['blocks']:
        plan.blocks.append(PlanBlock(**data))
    db.flush()

def save_edit(db: Session, plan: DayPlan, before: dict, action: str):
    redo = db.scalars(select(PlanHistory).where(PlanHistory.on_date == plan.on_date, PlanHistory.undone.is_(True))).all()
    for record in redo:
        db.delete(record)
    db.add(PlanHistory(on_date=plan.on_date, action=action, before=before,
                       after=as_state(plan), event_signature=calendar_hash(db, plan.on_date)))
    db.flush()
    all_rows = db.scalars(select(PlanHistory).where(PlanHistory.on_date == plan.on_date).order_by(PlanHistory.id.desc())).all()
    for row in all_rows[30:]:
        db.delete(row)
    db.commit()
    db.refresh(plan)
    return get_plan(db, plan.on_date)

def validate_slot(db: Session, plan: DayPlan, block: PlanBlock, start: int, end: int, ignored_ids: set[int] | None = None):
    if start < 0 or end > 1440 or end <= start or (start % 5 or end % 5):
        raise HTTPException(422, 'Час має бути кратним 5 хвилинам; кінець повинен бути після початку')
    pref = db.get(Preferences, 1)
    wake, sleep = (minutes(pref.wake_time), minutes(pref.sleep_time)) if pref else (480, 1410)
    if start < wake or end > sleep:
        raise HTTPException(409, 'Блок виходить за межі налаштованого часу неспання')
    ignored_ids = ignored_ids or set()
    for other in plan.blocks:
        if other.id == block.id or other.id in ignored_ids or other.status == 'skipped':
            continue
        if conflict(start, end, other.start_min, other.end_min):
            raise HTTPException(409, f'Перетин з «{other.title}» ({other.start_min//60:02d}:{other.start_min%60:02d}–{other.end_min//60:02d}:{other.end_min%60:02d})')

def get_block(db: Session, block_id: int) -> tuple[DayPlan, PlanBlock]:
    block = db.get(PlanBlock, block_id)
    if block is None:
        raise HTTPException(404, 'Блок не знайдено')
    plan = get_plan(db, db.get(DayPlan, block.plan_id).on_date)
    return plan, block

def edit_block(db: Session, block_id: int, data: BlockEditIn):
    plan, block = get_block(db, block_id)
    check_plan(db, plan)
    if block.kind not in EDITABLE or block.status == 'done':
        raise HTTPException(409, 'Зустрічі Google та завершені справи не можна пересувати')
    validate_slot(db, plan, block, data.start_min, data.end_min)
    before = as_state(plan)
    block.title, block.category = data.title, data.category
    block.start_min, block.end_min = data.start_min, data.end_min
    block.is_locked = data.is_locked
    block.explanation = 'Ручне налаштування часу' if block.kind != 'custom' else 'Власний блок користувача'
    return save_edit(db, plan, before, 'Редагування: ' + data.title[:70])

def create_custom(db: Session, data: CustomBlockIn):
    plan = get_plan(db, data.on_date)
    check_plan(db, plan)
    draft = PlanBlock(plan_id=plan.id, kind='custom', source_id=None, title=data.title,
                      category=data.category, start_min=data.start_min, end_min=data.end_min,
                      status='pending', explanation='Власний блок користувача', is_locked=data.is_locked)
    validate_slot(db, plan, draft, data.start_min, data.end_min)
    before = as_state(plan)
    plan.blocks.append(draft)
    return save_edit(db, plan, before, 'Додано: ' + data.title[:70])

def remove_custom(db: Session, block_id: int):
    plan, block = get_block(db, block_id)
    check_plan(db, plan)
    if block.kind != 'custom':
        raise HTTPException(409, 'Видаляти можна тільки вручну додані блоки')
    before = as_state(plan)
    plan.blocks.remove(block)
    return save_edit(db, plan, before, 'Видалено власний блок')

def lock_block(db: Session, block_id: int, locked: bool):
    plan, block = get_block(db, block_id)
    check_plan(db, plan)
    if block.kind not in EDITABLE:
        raise HTTPException(409, 'Час зовнішніх зустрічей завжди фіксований')
    before = as_state(plan)
    block.is_locked = locked
    return save_edit(db, plan, before, 'Закріплено час' if locked else 'Час розблоковано')

def reorder(db: Session, day: date, block_id: int, target_id: int):
    plan = get_plan(db, day)
    check_plan(db, plan)
    ordered = sorted(plan.blocks, key=lambda b: (b.start_min, b.id))
    idx = next((i for i, b in enumerate(ordered) if b.id == block_id), -1)
    dst = next((i for i, b in enumerate(ordered) if b.id == target_id), -1)
    if idx < 0 or dst < 0:
        raise HTTPException(404, 'Не знайдено блок для переміщення')
    if idx == dst:
        return plan
    lower, upper = sorted((idx, dst))
    segment = ordered[lower:upper + 1]
    if any(b.kind not in EDITABLE or b.is_locked or b.status != 'pending' for b in segment):
        raise HTTPException(409, 'Не можна перетягувати через зустріч, виконану або закріплену справу. Використайте редагування часу.')
    # Preserve original gaps and total time consumed; this cannot move a calendar event.
    gaps = [segment[i+1].start_min - segment[i].end_min for i in range(len(segment)-1)]
    changed = list(segment)
    moved = changed.pop(idx-lower)
    changed.insert(dst-lower, moved)
    starts = {}
    cursor = segment[0].start_min
    for i, block in enumerate(changed):
        starts[block.id] = (cursor, cursor + block.end_min - block.start_min)
        cursor = starts[block.id][1] + (gaps[i] if i < len(gaps) else 0)
    outside = {b.id for b in segment}
    # Check every proposed position against fixed/outside blocks and the daily window.
    for block in changed:
        start, end = starts[block.id]
        validate_slot(db, plan, block, start, end, outside)
    before = as_state(plan)
    for block in changed:
        block.start_min, block.end_min = starts[block.id]
        block.explanation = 'Порядок змінено вручну'
    return save_edit(db, plan, before, 'Змінено порядок активностей')

def history(db: Session, day: date):
    rows = db.scalars(select(PlanHistory).where(PlanHistory.on_date == day).order_by(PlanHistory.id.desc())).all()
    return {'undo_available': any(not h.undone for h in rows), 'redo_available': any(h.undone for h in rows),
            'entries': [{'id': r.id, 'action': r.action, 'undone': r.undone} for r in rows[:15]]}

def step_history(db: Session, day: date, direction: str):
    plan = get_plan(db, day)
    check_plan(db, plan)
    stmt = select(PlanHistory).where(PlanHistory.on_date == day, PlanHistory.undone.is_(direction == 'redo'))
    row = db.scalar(stmt.order_by(PlanHistory.id.desc() if direction == 'undo' else PlanHistory.id.asc()))
    if row is None:
        raise HTTPException(409, 'Немає змін, які можна ' + ('скасувати' if direction == 'undo' else 'повторити'))
    if row.event_signature != calendar_hash(db, day):
        raise HTTPException(409, 'Календар змінився; історію редагування не можна безпечно відновити')
    restore(db, plan, row.before if direction == 'undo' else row.after)
    row.undone = direction == 'undo'
    db.commit()
    return get_plan(db, day)

def reset_history(db: Session, day: date):
    db.execute(delete(PlanHistory).where(PlanHistory.on_date == day))
