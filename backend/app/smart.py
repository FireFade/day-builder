"""Local-only v1.0: structured work, goals, habits and richer task rules."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .db import get_db
from .models import Activity, ActivityPolicy, DayPlan, DayTemplate, Goal, Habit, HabitCheck, InboxTask, PlanBlock
from .schemas import minutes

router = APIRouter(prefix='/api', tags=['Smart Planning'])

def stale(db):
    db.execute(update(DayPlan).values(calendar_stale=True))

def missing(db, model, pk):
    row=db.get(model, pk)
    if row is None: raise HTTPException(404, 'Запис не знайдено')
    return row

class PolicyIn(BaseModel):
    due_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    repeat_every_days: int = Field(default=1, ge=1, le=365)
    preferred_start: str | None = None
    energy: int = Field(default=3, ge=1, le=5)
    prep_minutes: int = Field(default=0, ge=0, le=180, multiple_of=15)
    travel_minutes: int = Field(default=0, ge=0, le=180, multiple_of=15)
    break_after_minutes: int = Field(default=0, ge=0, le=120, multiple_of=15)
    depends_on: list[int] = Field(default_factory=list, max_length=25)
    goal_id: int | None = None
    @model_validator(mode='after')
    def validate(self):
        if any(d<0 or d>6 for d in self.weekdays) or len(self.weekdays)!=len(set(self.weekdays)):
            raise ValueError('Дні тижня: 0=Пн … 6=Нд, без повторів')
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError('Дата завершення раніше початку')
        if self.preferred_start: minutes(self.preferred_start)
        if len(self.depends_on)!=len(set(self.depends_on)):
            raise ValueError('Залежності не можуть дублюватися')
        return self

class PolicyOut(PolicyIn):
    model_config=ConfigDict(from_attributes=True)
    activity_id:int

@router.get('/policies', response_model=list[PolicyOut])
def all_policies(db:Session=Depends(get_db)):
    return db.scalars(select(ActivityPolicy)).all()

@router.put('/policies/{activity_id}', response_model=PolicyOut)
def set_policy(activity_id:int,data:PolicyIn,db:Session=Depends(get_db)):
    act=missing(db,Activity,activity_id)
    if act.recurrence=='once' and data.weekdays: raise HTTPException(422,'Разове завдання не потребує днів тижня')
    if activity_id in data.depends_on: raise HTTPException(422,'Самозалежність заборонена')
    if data.goal_id is not None: missing(db,Goal,data.goal_id)
    ids=set(db.scalars(select(Activity.id)).all())
    if any(k not in ids for k in data.depends_on): raise HTTPException(422,'Залежність посилається на неіснуюче завдання')
    # Validate graph with candidate edges before storing it.
    graph={p.activity_id:list(p.depends_on or []) for p in db.scalars(select(ActivityPolicy)).all()}
    graph[activity_id]=data.depends_on
    def visit(node, stack, seen):
        if node in stack: raise HTTPException(422,'Циклічні залежності завдань заборонені')
        if node in seen:return
        stack.add(node)
        for dependency in graph.get(node,[]):visit(dependency,stack,seen)
        stack.remove(node);seen.add(node)
    seen=set()
    for node in graph:visit(node,set(),seen)
    p=db.scalar(select(ActivityPolicy).where(ActivityPolicy.activity_id==activity_id))
    if not p:p=ActivityPolicy(activity_id=activity_id);db.add(p)
    for k,v in data.model_dump().items():setattr(p,k,v)
    stale(db);db.commit();db.refresh(p)
    return p

class TaskIn(BaseModel):
    title: str = Field(min_length=1,max_length=160)
    notes: str = Field(default='',max_length=2000)
    due_date: date | None = None
    priority: int = Field(default=3,ge=1,le=5)
    duration_minutes: int = Field(default=30,ge=15,le=480,multiple_of=15)
    parent_id: int | None = None
    goal_id: int | None = None
class TaskOut(TaskIn):
    model_config=ConfigDict(from_attributes=True)
    id:int
    state:str
    activity_id:int|None

@router.get('/inbox',response_model=list[TaskOut])
def list_tasks(db:Session=Depends(get_db)):
    return db.scalars(select(InboxTask).order_by(InboxTask.id.desc())).all()

@router.post('/inbox',response_model=TaskOut,status_code=201)
def add_task(data:TaskIn,db:Session=Depends(get_db)):
    if data.parent_id is not None: missing(db,InboxTask,data.parent_id)
    if data.goal_id is not None: missing(db,Goal,data.goal_id)
    t=InboxTask(**data.model_dump());db.add(t);db.commit();db.refresh(t);return t

@router.put('/inbox/{task_id}',response_model=TaskOut)
def edit_task(task_id:int,data:TaskIn,db:Session=Depends(get_db)):
    t=missing(db,InboxTask,task_id)
    if data.parent_id==task_id:raise HTTPException(422,'Завдання не може бути власним підзавданням')
    if data.parent_id is not None:
        node=data.parent_id;seen={task_id}
        while node is not None:
            if node in seen:raise HTTPException(422,'Циклічна структура підзавдань')
            seen.add(node);parent=missing(db,InboxTask,node);node=parent.parent_id
    if data.goal_id is not None:missing(db,Goal,data.goal_id)
    for k,v in data.model_dump().items():setattr(t,k,v)
    db.commit();db.refresh(t);return t

@router.patch('/inbox/{task_id}/state',response_model=TaskOut)
def task_state(task_id:int,state:str,db:Session=Depends(get_db)):
    if state not in ('inbox','done','archived'):raise HTTPException(422,'Невідомий статус')
    t=missing(db,InboxTask,task_id);t.state=state;db.commit();db.refresh(t);return t

@router.delete('/inbox/{task_id}',status_code=204)
def remove_task(task_id:int,db:Session=Depends(get_db)):
    t=missing(db,InboxTask,task_id)
    db.query(InboxTask).filter(InboxTask.parent_id==task_id).update({'parent_id':None})
    db.delete(t);db.commit()

class PromoteIn(BaseModel):
    on_date:date
    category:str='personal'
    required:bool=True
@router.post('/inbox/{task_id}/schedule',response_model=TaskOut)
def schedule_task(task_id:int,data:PromoteIn,db:Session=Depends(get_db)):
    t=missing(db,InboxTask,task_id)
    if t.state=='archived': raise HTTPException(409,'Архівоване завдання не можна планувати')
    if t.activity_id is not None:raise HTTPException(409,'Завдання вже перетворене на активність')
    if data.category not in ('personal','work','study','health','leisure'):raise HTTPException(422,'Категорія невідома')
    a=Activity(title=t.title,description=t.notes,category=data.category,duration_minutes=t.duration_minutes,
       priority=t.priority,required=data.required,earliest_start='08:00',latest_end='23:00',
       recurrence='once',target_date=data.on_date,enabled=True)
    db.add(a);db.flush();t.activity_id=a.id;t.state='done'
    if t.goal_id is not None:db.add(ActivityPolicy(activity_id=a.id,goal_id=t.goal_id))
    stale(db);db.commit();db.refresh(t);return t

class GoalIn(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    description:str=Field(default='',max_length=2000)
    target_minutes_week:int=Field(default=120,ge=15,le=10080)
    due_date:date|None=None
    archived:bool=False
class GoalOut(GoalIn):
    model_config=ConfigDict(from_attributes=True)
    id:int
@router.get('/goals',response_model=list[GoalOut])
def goals(db:Session=Depends(get_db)):
    return db.scalars(select(Goal).order_by(Goal.id.desc())).all()
@router.post('/goals',response_model=GoalOut,status_code=201)
def add_goal(data:GoalIn,db:Session=Depends(get_db)):
    r=Goal(**data.model_dump());db.add(r);db.commit();db.refresh(r);return r
@router.put('/goals/{pk}',response_model=GoalOut)
def put_goal(pk:int,data:GoalIn,db:Session=Depends(get_db)):
    r=missing(db,Goal,pk)
    for k,v in data.model_dump().items():setattr(r,k,v)
    db.commit();db.refresh(r);return r
@router.delete('/goals/{pk}',status_code=204)
def delete_goal(pk:int,db:Session=Depends(get_db)):
    r=missing(db,Goal,pk)
    db.query(ActivityPolicy).filter(ActivityPolicy.goal_id==pk).update({'goal_id':None})
    db.query(InboxTask).filter(InboxTask.goal_id==pk).update({'goal_id':None})
    db.delete(r);db.commit()

class HabitIn(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    weekdays:list[int]=Field(default_factory=lambda:list(range(7)),min_length=1,max_length=7)
    minutes:int=Field(default=15,ge=5,le=480)
    enabled:bool=True
    linked_activity_id:int|None=None
    @model_validator(mode='after')
    def validate(self):
        if len(set(self.weekdays))!=len(self.weekdays) or any(d not in range(7) for d in self.weekdays):
            raise ValueError('Невірні дні тижня')
        return self
class HabitOut(HabitIn):
    model_config=ConfigDict(from_attributes=True)
    id:int
@router.get('/habits')
def habit_progress(on_date:date,db:Session=Depends(get_db)):
    records=db.scalars(select(Habit)).all()
    since=on_date-timedelta(days=29)
    checks=db.scalars(select(HabitCheck).where(HabitCheck.on_date>=since,HabitCheck.on_date<=on_date)).all()
    ids={(c.habit_id,c.on_date) for c in checks}
    return [{'id':r.id,'title':r.title,'weekdays':r.weekdays,'minutes':r.minutes,'enabled':r.enabled,
             'linked_activity_id':r.linked_activity_id,'checked':(r.id,on_date) in ids,
             'completed_last_30':sum((r.id,since+timedelta(days=i)) in ids for i in range(30))} for r in records]
@router.post('/habits',response_model=HabitOut,status_code=201)
def add_habit(data:HabitIn,db:Session=Depends(get_db)):
    if data.linked_activity_id is not None:missing(db,Activity,data.linked_activity_id)
    r=Habit(**data.model_dump());db.add(r);db.commit();db.refresh(r);return r
@router.put('/habits/{pk}',response_model=HabitOut)
def update_habit(pk:int,data:HabitIn,db:Session=Depends(get_db)):
    r=missing(db,Habit,pk)
    if data.linked_activity_id is not None:missing(db,Activity,data.linked_activity_id)
    for k,v in data.model_dump().items():setattr(r,k,v)
    db.commit();db.refresh(r);return r
@router.delete('/habits/{pk}',status_code=204)
def delete_habit(pk:int,db:Session=Depends(get_db)):
    r=missing(db,Habit,pk)
    db.query(HabitCheck).filter(HabitCheck.habit_id==pk).delete()
    db.delete(r);db.commit()
@router.put('/habits/{pk}/check')
def check_habit(pk:int,on_date:date,checked:bool=True,db:Session=Depends(get_db)):
    r=missing(db,Habit,pk)
    if on_date.weekday() not in (r.weekdays or []):raise HTTPException(409,'Звичка не запланована на цей день')
    existing=db.scalar(select(HabitCheck).where(HabitCheck.habit_id==pk,HabitCheck.on_date==on_date))
    if checked and not existing:db.add(HabitCheck(habit_id=pk,on_date=on_date))
    if not checked and existing:db.delete(existing)
    db.commit();return {'checked':checked,'habit_id':pk,'on_date':on_date.isoformat()}

class TemplateIn(BaseModel):
    title:str=Field(min_length=1,max_length=100)
    on_date:date
@router.get('/templates')
def templates(db:Session=Depends(get_db)):
    return [{'id':x.id,'title':x.title,'blocks_count':len(x.blocks or [])} for x in db.scalars(select(DayTemplate)).all()]
@router.post('/templates',status_code=201)
def save_template(data:TemplateIn,db:Session=Depends(get_db)):
    p=db.scalar(select(DayPlan).where(DayPlan.on_date==data.on_date))
    if not p:raise HTTPException(404,'Спочатку збережіть план дня')
    blocks=db.scalars(select(PlanBlock).where(PlanBlock.plan_id==p.id,PlanBlock.kind.in_(['custom','activity','meal']))).all()
    # No external calendar information is copied into templates.
    snap=[{'title':b.title,'category':b.category,'start_min':b.start_min,'end_min':b.end_min} for b in blocks]
    r=DayTemplate(title=data.title,blocks=snap);db.add(r);db.commit();db.refresh(r)
    return {'id':r.id,'title':r.title,'blocks_count':len(snap)}
@router.post('/templates/{pk}/apply')
def apply_template(pk:int,on_date:date,db:Session=Depends(get_db)):
    from .manual_plan import check_plan, get_plan, as_state, save_edit
    record=missing(db,DayTemplate,pk)
    plan=get_plan(db,on_date)
    check_plan(db,plan)
    before=as_state(plan)
    from .models import Preferences,CalendarEvent
    from .planner import conflict
    from .schemas import minutes
    prefs=db.get(Preferences,1)
    if prefs is None:raise HTTPException(409,'Спочатку налаштуйте свій день')
    low,high=minutes(prefs.wake_time),minutes(prefs.sleep_time)
    occupied=[(b.start_min,b.end_min) for b in plan.blocks]
    # Atomic dry-run before creating any template block.
    new=[]
    for item in record.blocks:
        a,b=item['start_min'],item['end_min']
        if not(low<=a<b<=high) or any(conflict(a,b,c,d) for c,d in occupied):
            raise HTTPException(409,f'Шаблон конфліктує з поточним днем: {item["title"]}')
        occupied.append((a,b));new.append(item)
    for item in new:
        plan.blocks.append(PlanBlock(kind='custom',source_id=None,title=item['title'],category=item['category'],
          start_min=item['start_min'],end_min=item['end_min'],status='pending',is_locked=True,
          explanation='Додано з шаблону: закріплений блок'))
    save_edit(db,plan,before,'Шаблон: '+record.title)
    return {'added':len(new),'date':on_date.isoformat()}
@router.delete('/templates/{pk}',status_code=204)
def delete_template(pk:int,db:Session=Depends(get_db)):
    db.delete(missing(db,DayTemplate,pk));db.commit()

@router.get('/goals/progress')
def goal_progress(on_date:date,db:Session=Depends(get_db)):
    monday=on_date-timedelta(days=on_date.weekday())
    through=monday+timedelta(days=6)
    plans=db.scalars(select(DayPlan).where(DayPlan.on_date>=monday,DayPlan.on_date<=through)).all()
    ids={p.id for p in plans}
    completed=db.scalars(select(PlanBlock).where(PlanBlock.plan_id.in_(ids),PlanBlock.kind=='activity',PlanBlock.status=='done')).all() if ids else []
    policies={p.activity_id:p for p in db.scalars(select(ActivityPolicy)).all()}
    amounts={}
    for block in completed:
        link=policies.get(block.source_id)
        if link and link.goal_id:
            amounts[link.goal_id]=amounts.get(link.goal_id,0)+block.end_min-block.start_min
    return [{'id':g.id,'title':g.title,'target_minutes_week':g.target_minutes_week,
      'done_minutes_week':amounts.get(g.id,0),
      'completion_percent':round(100*amounts.get(g.id,0)/max(g.target_minutes_week,1)),
      'monday':monday.isoformat()} for g in db.scalars(select(Goal)).all()]
