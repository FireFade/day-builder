"""Local single-user API; DO NOT expose on the public internet without authentication."""
from datetime import date
from pydantic import BaseModel, Field
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from .db import get_db
from .models import Activity, ActivityPolicy, CalendarEvent, DayPlan, Habit, InboxTask, PlanBlock, Preferences, DEFAULT_MEALS
from .planner import generate
from .schemas import ActivityIn, ActivityOut, BlockOut, BlockStatusIn, EventIn, EventOut, PlanGenerate, PlanOut, PreferencesIn

from .integrations.background import lifecycle
app = FastAPI(title="Day Builder API", version="1.0.0-beta", description="Local-only daily planner and calendar sync", lifespan=lifecycle)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"], allow_headers=["Content-Type"])


def preferences(db: Session) -> Preferences:
    record = db.get(Preferences, 1)
    if record is None:
        record = Preferences(id=1, meals=[dict(x) for x in DEFAULT_MEALS])
        db.add(record)
        db.commit()
        db.refresh(record)
    return record

@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "local-only", "calendar_integrations": "google-and-microsoft-configurable"}

@app.get("/api/settings", response_model=PreferencesIn)
def get_settings(db: Session = Depends(get_db)):
    return preferences(db)

@app.put("/api/settings", response_model=PreferencesIn)
def update_settings(data: PreferencesIn, db: Session = Depends(get_db)):
    record = preferences(db)
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record

@app.get("/api/activities", response_model=list[ActivityOut])
def get_activities(db: Session = Depends(get_db)):
    return db.scalars(select(Activity).order_by(Activity.id.desc())).all()

def mark_activity_plans_stale(db: Session):
    """An activity change can affect any previously generated day."""
    db.execute(update(DayPlan).values(calendar_stale=True))

@app.post("/api/activities", response_model=ActivityOut, status_code=201)
def add_activity(data: ActivityIn, db: Session = Depends(get_db)):
    record = Activity(**data.model_dump())
    db.add(record)
    mark_activity_plans_stale(db)
    db.commit()
    db.refresh(record)
    return record

@app.put("/api/activities/{activity_id}", response_model=ActivityOut)
def edit_activity(activity_id: int, data: ActivityIn, db: Session = Depends(get_db)):
    record = db.get(Activity, activity_id)
    if record is None:
        raise HTTPException(404, "Activity not found")
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    mark_activity_plans_stale(db)
    db.commit()
    db.refresh(record)
    return record

@app.delete("/api/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    record = db.get(Activity, activity_id)
    if record is None:
        raise HTTPException(404, "Activity not found")
    db.query(ActivityPolicy).filter(ActivityPolicy.activity_id==activity_id).delete()
    # Keep user-owned records and plan history, but remove links to the deleted template.
    db.query(InboxTask).filter(InboxTask.activity_id==activity_id).update(
        {"activity_id": None, "state": "inbox"}, synchronize_session=False
    )
    db.query(Habit).filter(Habit.linked_activity_id==activity_id).update(
        {"linked_activity_id": None}, synchronize_session=False
    )
    db.delete(record)
    mark_activity_plans_stale(db)
    db.commit()

@app.get("/api/events", response_model=list[EventOut])
def get_events(on_date: date | None = None, db: Session = Depends(get_db)):
    statement = select(CalendarEvent)
    if on_date:
        statement = statement.where(CalendarEvent.on_date == on_date)
    return db.scalars(statement.order_by(CalendarEvent.on_date, CalendarEvent.start_time)).all()

@app.post("/api/events", response_model=EventOut, status_code=201)
def add_event(data: EventIn, db: Session = Depends(get_db)):
    record = CalendarEvent(**data.model_dump(), source="manual")
    db.add(record)
    existing_plan = load_plan(db, data.on_date)
    if existing_plan:
        existing_plan.calendar_stale = True
    db.commit()
    db.refresh(record)
    return record

@app.put("/api/events/{event_id}", response_model=EventOut)
def edit_event(event_id: int, data: EventIn, db: Session = Depends(get_db)):
    record = db.get(CalendarEvent, event_id)
    if record is None:
        raise HTTPException(404, "Event not found")
    if record.source != 'manual':
        raise HTTPException(409, 'Зовнішні події редагуйте у відповідному календарі')
    old_date = record.on_date
    record.title, record.on_date = data.title, data.on_date
    record.start_time, record.end_time = data.start_time, data.end_time
    for day in {old_date, data.on_date}:
        existing_plan = load_plan(db, day)
        if existing_plan:
            existing_plan.calendar_stale = True
    db.commit()
    db.refresh(record)
    return record

@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    record = db.get(CalendarEvent, event_id)
    if record is None:
        raise HTTPException(404, "Event not found")
    if record.source != "manual":
        raise HTTPException(409, "Зовнішні календарні події можна видалити лише в їхньому календарі")
    old_date = record.on_date
    db.delete(record)
    existing_plan = load_plan(db, old_date)
    if existing_plan:
        existing_plan.calendar_stale = True
    db.commit()

def load_plan(db: Session, on_date: date):
    return db.scalar(select(DayPlan).where(DayPlan.on_date == on_date).options(selectinload(DayPlan.blocks)))

@app.get("/api/plans/{on_date}", response_model=PlanOut | None)
def get_plan(on_date: date, db: Session = Depends(get_db)):
    return load_plan(db, on_date)

# Preview is read-only. Apply must confirm the same state revision to avoid
# silently overwriting a user's plan after a late calendar sync.
from .plan_preview import preview as preview_proposal
from .manual_plan import reset_history

class PlanApply(PlanGenerate):
    revision: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")

@app.post("/api/plans/preview")
def preview_plan(data: PlanGenerate, db: Session = Depends(get_db)):
    return preview_proposal(db, data.on_date)

@app.post("/api/plans/apply", response_model=PlanOut)
def apply_plan(data: PlanApply, db: Session = Depends(get_db)):
    proposal = preview_proposal(db, data.on_date)
    if proposal["revision"] != data.revision:
        raise HTTPException(409, "Дані розкладу змінилися. Створіть новий попередній перегляд перед підтвердженням.")
    current_plan = load_plan(db, data.on_date)
    reset_history(db, data.on_date)
    if current_plan:
        db.delete(current_plan)
        db.flush()
    saved = DayPlan(on_date=data.on_date, warnings=proposal["warnings"])
    saved.blocks = [PlanBlock(**block) for block in proposal["blocks"]]
    db.add(saved)
    db.commit()
    return load_plan(db, data.on_date)

@app.post("/api/plans/generate", response_model=PlanOut)
def generate_plan(data: PlanGenerate, db: Session = Depends(get_db)):
    current_plan = load_plan(db, data.on_date)
    completed = [block for block in current_plan.blocks if block.status == "done" and block.kind == "activity"] if current_plan else []
    preserved = [block for block in current_plan.blocks if block not in completed and
                 ((block.is_locked and block.kind in ('activity','meal','custom')) or block.kind == 'custom')
                 and block.status != 'skipped'] if current_plan else []
    skipped = [block.source_id for block in current_plan.blocks if block.kind == 'activity' and block.status == 'skipped'] if current_plan else []
    activities = db.scalars(select(Activity)).all()
    events = db.scalars(select(CalendarEvent).where(CalendarEvent.on_date == data.on_date)).all()
    policies={p.activity_id:p for p in db.scalars(select(ActivityPolicy)).all()}
    blocks, warnings = generate(data.on_date, preferences(db), activities, events, completed, preserved, skipped, policies)
    reset_history(db, data.on_date)
    if current_plan:
        db.delete(current_plan)
        db.flush()
    current_plan = DayPlan(on_date=data.on_date, warnings=warnings)
    current_plan.blocks = [PlanBlock(**block) for block in blocks]
    db.add(current_plan)
    db.commit()
    return load_plan(db, data.on_date)

@app.patch("/api/plans/blocks/{block_id}", response_model=BlockOut)
def update_block(block_id: int, data: BlockStatusIn, db: Session = Depends(get_db)):
    block = db.get(PlanBlock, block_id)
    if block is None:
        raise HTTPException(404, "Block not found")
    if block.kind != "activity":
        raise HTTPException(400, "Only activities can be marked done or skipped")
    from .manual_plan import as_state, save_edit, get_plan, check_plan
    plan = get_plan(db, db.get(DayPlan, block.plan_id).on_date)
    check_plan(db, plan)
    before = as_state(plan)
    block.status = data.status
    save_edit(db, plan, before, 'Статус: ' + block.title[:65])
    return block


# v0.5 — edit the day's timeline without touching source calendars.
from .schemas import BlockEditIn, CustomBlockIn, MoveBlockIn, LockBlockIn
from .manual_plan import edit_block, create_custom, remove_custom, lock_block, reorder, history, step_history

@app.put("/api/plans/blocks/{block_id}/edit", response_model=PlanOut)
def manual_edit(block_id: int, data: BlockEditIn, db: Session = Depends(get_db)):
    return edit_block(db, block_id, data)

@app.post("/api/plans/blocks", response_model=PlanOut, status_code=201)
def manual_add(data: CustomBlockIn, db: Session = Depends(get_db)):
    return create_custom(db, data)

@app.delete("/api/plans/blocks/{block_id}/custom", response_model=PlanOut)
def manual_delete(block_id: int, db: Session = Depends(get_db)):
    return remove_custom(db, block_id)

@app.patch("/api/plans/blocks/{block_id}/lock", response_model=PlanOut)
def manual_lock(block_id: int, data: LockBlockIn, db: Session = Depends(get_db)):
    return lock_block(db, block_id, data.is_locked)

@app.post("/api/plans/reorder", response_model=PlanOut)
def manual_reorder(data: MoveBlockIn, db: Session = Depends(get_db)):
    return reorder(db, data.on_date, data.block_id, data.target_id)

@app.get("/api/plans/{on_date}/history")
def edit_history(on_date: date, db: Session = Depends(get_db)):
    return history(db, on_date)

@app.post("/api/plans/{on_date}/undo", response_model=PlanOut)
def undo_plan(on_date: date, db: Session = Depends(get_db)):
    return step_history(db, on_date, 'undo')

@app.post("/api/plans/{on_date}/redo", response_model=PlanOut)
def redo_plan(on_date: date, db: Session = Depends(get_db)):
    return step_history(db, on_date, 'redo')

@app.get("/api/plans/{on_date}/export.ics")
def export_ics(on_date: date, db: Session = Depends(get_db)):
    from .export import export_calendar
    return export_calendar(get_db=db, on_date=on_date)

# No-build offline interface. Local URL: http://127.0.0.1:8000/
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(WEB_DIR / "index.html")
    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(WEB_DIR / "sw.js", media_type="application/javascript", headers={"Cache-Control":"no-cache", "Service-Worker-Allowed":"/"})

# Read-only Google / Microsoft calendar integration endpoints
from .integrations.routes import router as calendar_router
app.include_router(calendar_router)

# v0.6 — weekly planning, factual insights, focus records, daily check-in
from datetime import timedelta
from .schemas import WeekApplyIn, FocusSessionIn, FocusSessionOut, ReflectionIn, ReflectionOut
from .models import FocusSession, DayReflection
from .week import week_view, apply_week
from .insights import get_insights

@app.get('/api/week/{on_date}')
def preview_week(on_date: date, db: Session = Depends(get_db)):
    return week_view(db, on_date)

@app.post('/api/week/apply')
def confirm_week(data: WeekApplyIn, db: Session = Depends(get_db)):
    return apply_week(db, data)

@app.get('/api/insights')
def insights(end_date: date, days: int = 7, db: Session = Depends(get_db)):
    if days not in (7, 30, 90):
        raise HTTPException(422, 'Оберіть 7, 30 або 90 днів')
    return get_insights(db, end_date, days)

@app.get('/api/focus', response_model=list[FocusSessionOut])
def focus_history(on_date: date | None = None, db: Session = Depends(get_db)):
    query=select(FocusSession)
    if on_date is not None:
        query=query.where(FocusSession.on_date==on_date)
    return db.scalars(query.order_by(FocusSession.id.desc()).limit(100)).all()

@app.post('/api/focus', response_model=FocusSessionOut, status_code=201)
def save_focus(data: FocusSessionIn, db: Session = Depends(get_db)):
    record=FocusSession(**data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@app.delete('/api/focus/{session_id}', status_code=204)
def delete_focus(session_id: int, db: Session = Depends(get_db)):
    record=db.get(FocusSession,session_id)
    if record is None: raise HTTPException(404, 'Фокус-сесію не знайдено')
    db.delete(record)
    db.commit()

@app.get('/api/reflections/{on_date}', response_model=ReflectionOut | None)
def get_reflection(on_date: date, db: Session = Depends(get_db)):
    return db.scalar(select(DayReflection).where(DayReflection.on_date==on_date))

@app.put('/api/reflections/{on_date}', response_model=ReflectionOut)
def put_reflection(on_date: date, data: ReflectionIn, db: Session = Depends(get_db)):
    record=db.scalar(select(DayReflection).where(DayReflection.on_date==on_date))
    if record is None:
        record=DayReflection(on_date=on_date,**data.model_dump())
        db.add(record)
    else:
        for k,v in data.model_dump().items():setattr(record,k,v)
    db.commit()
    db.refresh(record)
    return record

# v1.0 feature endpoints, kept separate for maintainability
from .smart import router as smart_router
app.include_router(smart_router)
from .local_system import router as local_system_router
app.include_router(local_system_router)
