import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity as ActivityIcon, AlarmClock, ArrowDownRight, ArrowRight,  CalendarDays, Check, CheckCheck, ChevronLeft, ChevronRight, CircleAlert, Clock, Coffee, Compass, Flame, HeartPulse, LayoutDashboard, ListTodo, Moon,  Pencil, Plus, RefreshCw, Settings2, Sparkles, Sunrise, Trash2, WandSparkles, X } from 'lucide-react'
import { Activity, api, Block, Category, currentLocalDay, Event, json, Meal, minuteLabel, Plan, PlanProposal, Preferences, ukDate } from './api'

type Page = 'dashboard'|'my-day'|'activities'|'calendar'|'settings'
type Modal = 'activity'|'event'|null
const catInfo: Record<Category, {name: string; tone: string; icon: string}> = {
  work: {name:'Робота', tone:'blue', icon:'💼'}, study:{name:'Навчання', tone:'violet',icon:'📚'},
  health:{name:'Здоров’я', tone:'green',icon:'💚'}, personal:{name:'Особисте', tone:'orange',icon:'⭐'}, leisure:{name:'Відпочинок',tone:'pink',icon:'🌿'},
}
const emptyActivity = (date: string): Omit<Activity,'id'> => ({ title:'', description:'', category:'personal', duration_minutes:60, priority:3, required:true, earliest_start:'08:00', latest_end:'23:00', recurrence:'daily', target_date:date, enabled:true })
const fmtDate = (dt: string) => new Intl.DateTimeFormat('uk-UA', {weekday:'long', day:'numeric', month:'long'}).format(new Date(dt+'T12:00:00Z'))
function shiftDay(date: string, amount: number) { const d = new Date(date+'T12:00:00Z'); d.setUTCDate(d.getUTCDate()+amount); return d.toISOString().slice(0,10) }

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [date, setDate] = useState(currentLocalDay())
  const [activities, setActivities] = useState<Activity[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [prefs, setPrefs] = useState<Preferences|null>(null)
  const [plan, setPlan] = useState<Plan|null>(null)
  const [proposal, setProposal] = useState<PlanProposal|null>(null)
  const [modal, setModal] = useState<Modal>(null)
  const [form, setForm] = useState<Omit<Activity,'id'>>(emptyActivity(currentLocalDay()))
  const [editing, setEditing] = useState<number|null>(null)
  const [eventForm, setEventForm] = useState({title:'',start_time:'10:00',end_time:'11:00'})
  const [message, setMessage] = useState<string|null>(null)
  const [error, setError] = useState<string|null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [stale, setStale] = useState(false)

  const notify = (text: string) => {setMessage(text); setError(null)}
  const fail = (err: unknown) => {setError(err instanceof Error ? err.message : String(err)); setMessage(null)}
  const refresh = async (day = date) => {
    try {
      const [a,e,p,s] = await Promise.all([
        api<Activity[]>('/activities'), api<Event[]>(`/events?on_date=${day}`),
        api<Plan|null>(`/plans/${day}`), api<Preferences>('/settings'),
      ])
      setActivities(a);setEvents(e);setPlan(p);setPrefs(s);setError(null)
    } catch (e) { fail(e) } finally {setLoading(false)}
  }
  useEffect(() => { setProposal(null); void refresh(date) }, [date]) // eslint-disable-line react-hooks/exhaustive-deps
  const build = async () => {
    setBusy(true)
    try { const p = await api<PlanProposal>('/plans/preview',json('POST',{on_date:date}));setProposal(p) }
    catch(e){fail(e)}finally{setBusy(false)}
  }
  const applyProposal = async () => {
    if (!proposal)return
    setBusy(true)
    try {
      const p = await api<Plan>('/plans/apply',json('POST',{on_date:proposal.on_date,revision:proposal.revision}))
      setPlan(p);setProposal(null);setStale(false)
      notify(p.warnings.length ? 'План застосовано з попередженнями' : 'Новий розклад підтверджено!')
    } catch(e){setProposal(null);fail(e)}finally{setBusy(false)}
  }
  const saveActivity = async () => {
    if (!form.title.trim()) {fail('Вкажіть назву активності');return}
    setBusy(true)
    try {
      const payload = {...form, title:form.title.trim(),target_date:form.recurrence==='once'?form.target_date:null}
      await api(`/activities${editing ? `/${editing}`:''}`,json(editing?'PUT':'POST',payload))
      setModal(null);setEditing(null);setStale(true);await refresh();notify(editing?'Активність оновлена. Перебудуйте день.':'Активність додано. Перебудуйте день.')
    } catch(e){fail(e)}finally{setBusy(false)}
  }
  const removeActivity = async (id: number) => {
    if (!window.confirm('Видалити активність?')) return
    try { await api(`/activities/${id}`,{method:'DELETE'}); setStale(true); await refresh(); notify('Активність видалено. Перебудуйте день.') } catch(e){fail(e)}
  }
  const saveEvent = async () => {
    if (!eventForm.title.trim()) {fail('Вкажіть назву зустрічі');return}
    setBusy(true)
    try {
      await api('/events',json('POST',{...eventForm,title:eventForm.title.trim(),on_date:date}))
      setModal(null);setStale(true);await refresh();notify('Подію додано. Перебудуйте день.')
    }catch(e){fail(e)}finally{setBusy(false)}
  }
  const removeEvent = async (id: number) => {
    if (!window.confirm('Видалити подію?'))return
    try {await api(`/events/${id}`,{method:'DELETE'});setStale(true);await refresh();notify('Подію видалено. Перебудуйте день.')}catch(e){fail(e)}
  }
  const toggle = async (block: Block) => {
    try { const newStatus = block.status==='done'?'pending':'done'; await api(`/plans/blocks/${block.id}`,json('PATCH',{status:newStatus}));await refresh();notify(newStatus==='done'?'Чудово! Активність виконано.':'Активність повернуто в план.') }
    catch(e){fail(e)}
  }
  const saveSettings = async () => {
    if (!prefs)return
    setBusy(true)
    try {const saved = await api<Preferences>('/settings',json('PUT',prefs));setPrefs(saved);setStale(true);notify('Налаштування збережено. Перебудуйте день.')}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  const openActivity = (item?: Activity) => {
    setEditing(item?.id ?? null)
    if(item){const {id:_,...copy}=item;void _;setForm(copy)}else setForm(emptyActivity(date))
    setModal('activity');setMessage(null);setError(null)
  }
  const categoryStat = (category: string) => plan?.blocks.filter(b=>b.category===category).length||0
  const completed = plan?.blocks.filter(b=>b.kind==='activity'&&b.status==='done').length||0
  const planned = plan?.blocks.filter(b=>b.kind==='activity').length||0
  const busyMinutes = plan?.blocks.reduce((sum,b)=>sum+b.end_min-b.start_min,0)||0
  const dayLength = prefs ? Number(prefs.sleep_time.slice(0,2))*60+Number(prefs.sleep_time.slice(3))-(Number(prefs.wake_time.slice(0,2))*60+Number(prefs.wake_time.slice(3))) : 930
  const percentage = Math.min(100,Math.round(busyMinutes/Math.max(dayLength,1)*100))
  const next = useMemo(()=>plan?.blocks.find(b=>b.kind==='activity'&&b.status==='pending')||null,[plan])
  const sidebar = [
    {id:'dashboard' as Page,label:'Огляд',Icon:LayoutDashboard},
    {id:'my-day' as Page,label:'Мій день',Icon:CalendarDays},
    {id:'activities' as Page,label:'Активності',Icon:ListTodo},
    {id:'calendar' as Page,label:'Календар',Icon:Clock},
    {id:'settings' as Page,label:'Налаштування',Icon:Settings2},
  ]
  const headings:Record<Page,{label:string;subtitle:string}>={
    dashboard:{label:'Твій день — у твоїх руках ✨',subtitle:'Сплануй важливе та залиш час для себе.'},
    'my-day':{label:'Мій день',subtitle:'Кожна активність на своєму місці.'},
    activities:{label:'Мої активності',subtitle:'Все, що потрібно та хочеться зробити.'},
    calendar:{label:'Календар подій',subtitle:'Фіксовані зустрічі, навколо яких будуємо день.'},
    settings:{label:'Мій ритм дня',subtitle:'Налаштуй сон, харчування та часовий пояс.'},
  }
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Compass size={24}/></div><div><b>day<span>builder</span></b><small>YOUR PERSONAL PLANNER</small></div></div>
      <div className="nav-caption">РОБОЧИЙ ПРОСТІР</div>
      <nav>{sidebar.map(({id,label,Icon})=><button key={id} className={'nav-item '+(page===id?'active':'')} onClick={()=>setPage(id)}><Icon size={19}/>{label}{page===id&&<span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="tip-art"><Sparkles size={18}/></div><b>Маленькі кроки — великі результати</b><p>Плануй реалістично. Виконуй важливе. Відпочивай без провини.</p><span>DAY BUILDER · LOCAL MVP</span></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumbs"><span>Day Builder</span><ChevronRight size={14}/><strong>{sidebar.find(x=>x.id===page)?.label}</strong></div><div className="top-actions"><span className="local-pill"><span className="online-dot"/>Локальний режим</span><span className="avatar">DB</span></div></header>
      <section className="body">
        <div className="heading"><div><div className="eyebrow"><span className="little-star">✦</span> ТВОЄ ПЛАНУВАННЯ, ТВОЇ ПРАВИЛА</div><h1>{headings[page].label}</h1><p>{headings[page].subtitle}</p></div><div className="date-picker"><button aria-label="Попередній день" onClick={()=>{setDate(shiftDay(date,-1));setStale(false)}}><ChevronLeft size={17}/></button><input aria-label="Дата" type="date" value={date} onChange={e=>{if(e.target.value){setDate(e.target.value);setStale(false)}}}/><button aria-label="Наступний день" onClick={()=>{setDate(shiftDay(date,1));setStale(false)}}><ChevronRight size={17}/></button></div></div>
        {(message||error)&&<div role="status" className={'notice '+(error?'danger':'success')}><span>{error||message}</span><button aria-label="Закрити повідомлення" onClick={()=>{setMessage(null);setError(null)}}><X size={16}/></button></div>}
        {stale&&<div className="notice amber"><CircleAlert size={18}/><span>Вхідні дані змінилися. Згенеруйте розклад ще раз, щоб врахувати їх.</span><button className="inline-link" onClick={build}>Перебудувати</button></div>}
        {loading ? <div className="empty"><RefreshCw className="spin" size={27}/>Завантаження...</div> : <>
          {page==='dashboard'&&<>
            <div className="hero"><div className="hero-text"><div className="hero-chip"><WandSparkles size={14}/> ВАШ РОЗУМНИЙ ПОМІЧНИК</div><h2>Зроби сьогодні<br/><span>саме те, що важливо.</span></h2><p>Ми допоможемо знайти найкращий час для справ, зустрічей і відпочинку — без перевантаження.</p><button className="button white" onClick={build} disabled={busy}><WandSparkles size={18}/>{busy?'Формуємо розклад...':plan?'Перебудувати мій день':'Побудувати мій день'} <ArrowRight size={18}/></button></div><div className="hero-graphic"><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="hero-center"><Sunrise size={42}/></div><div className="orbit-note note-one"><Check size={14}/> Все під контролем</div><div className="orbit-note note-two"><HeartPulse size={15}/> Баланс щодня</div><div className="tiny-star s1">✦</div><div className="tiny-star s2">✧</div></div></div>
            <div className="stat-grid"><Stat icon={<CheckCheck size={20}/>} tone="violet" title="Виконано справ" value={`${completed} / ${planned}`} info="активностей за день"/><Stat icon={<Clock size={20}/>} tone="blue" title="Заплановано" value={`${Math.floor(busyMinutes/60)} год ${busyMinutes%60} хв`} info="разом із зустрічами"/><Stat icon={<Flame size={20}/>} tone="orange" title="Зайнятість дня" value={`${percentage}%`} info="від часу неспання"/><Stat icon={<Coffee size={20}/>} tone="green" title="Для себе" value={String(categoryStat('leisure'))} info="запланованих занять"/></div>
            <div className="split"><section className="panel"><div className="panel-heading"><div><h3>План на сьогодні</h3><p>{fmtDate(date)}</p></div><button className="link" onClick={()=>setPage('my-day')}>Увесь день <ArrowRight size={15}/></button></div><Timeline blocks={plan?.blocks||[]} onToggle={toggle} compact/></section><section className="panel side-panel"><div className="panel-heading"><div><h3>У фокусі</h3><p>Що робити далі</p></div><span className="pill">МІЙ ПЛАН</span></div>{next?<div className="focus"><div className="focus-icon"><ActivityIcon size={26}/></div><span className="subtle">НАСТУПНА АКТИВНІСТЬ</span><h3>{next.title}</h3><p><Clock size={16}/>{minuteLabel(next.start_min)} — {minuteLabel(next.end_min)}</p><button className="button primary" onClick={()=>toggle(next)}><Check size={17}/>Позначити виконаною</button></div>:<div className="focus"><div className="focus-icon"><Sparkles size={26}/></div><h3>{plan?'Усе важливе зроблено!':'Ваш день ще не сплановано'}</h3><p>{plan?'Можна присвятити час відпочинку.':'Додайте активності та побудуйте розклад.'}</p><button className="button outlined" onClick={()=>setPage('activities')}>Мої активності <ArrowRight size={16}/></button></div>}<div className="quick-actions"><h4>Швидкі дії</h4><button onClick={()=>openActivity()}><Plus size={17}/>Додати активність <ArrowDownRight size={16}/></button><button onClick={()=>{setEventForm({title:'',start_time:'10:00',end_time:'11:00'});setModal('event')}}><CalendarDays size={17}/>Додати зустріч <ArrowDownRight size={16}/></button></div></section></div>
          </>}
          {page==='my-day'&&<><div className="action-row"><div><h2 className="content-title">{ukDate(date)}</h2><p className="muted">{plan?.blocks.length||0} блоків у розкладі · {planned} особистих активностей</p></div><button className="button primary" onClick={build} disabled={busy}><RefreshCw size={16}/>{busy?'Генеруємо...':'Згенерувати розклад'}</button></div>{plan&&plan.warnings.length>0&&<div className="warning-box"><div className="warning-heading"><CircleAlert size={19}/>Потрібна ваша увага</div>{plan.warnings.map((w,i)=><p key={i}>{w}</p>)}</div>}<div className="panel timeline-panel"><div className="panel-heading"><div><h3>Розклад дня</h3><p>Готовий план з урахуванням обмежень</p></div><span className="pill">{plan?'ЗБЕРЕЖЕНО':'НЕ СТВОРЕНО'}</span></div><Timeline blocks={plan?.blocks||[]} onToggle={toggle}/></div></>}
          {page==='activities'&&<><div className="action-row"><div><h2 className="content-title">Всі активності <span className="count">{activities.length}</span></h2><p className="muted">Обов’язкові та гнучкі завдання, з яких складається твій день.</p></div><button className="button primary" onClick={()=>openActivity()}><Plus size={18}/>Нова активність</button></div><div className="activities-grid">{activities.length?activities.map(a=><div className="activity-card" key={a.id}><div className="activity-top"><span className={'category-icon '+catInfo[a.category].tone}>{catInfo[a.category].icon}</span><div className="activity-actions"><button title="Редагувати" onClick={()=>openActivity(a)}><Pencil size={16}/></button><button title="Видалити" onClick={()=>removeActivity(a.id)}><Trash2 size={16}/></button></div></div><h3>{a.title}</h3><p className="activity-desc">{a.description||'Без опису'}</p><div className="tags"><span className={'chip '+catInfo[a.category].tone}>{catInfo[a.category].name}</span><span className={'chip '+(a.required?'required':'optional')}>{a.required?'Обов’язкова':'За бажанням'}</span></div><div className="activity-footer"><span><Clock size={15}/>{a.duration_minutes} хв</span><span><CalendarDays size={15}/>{a.earliest_start}–{a.latest_end}</span></div></div>):<div className="empty panel wide"><ListTodo size={38}/><h3>Поки що немає активностей</h3><p>Додай англійську, спорт, навчання або будь-яку іншу справу.</p><button className="button primary" onClick={()=>openActivity()}><Plus size={17}/>Додати першу активність</button></div>}</div></>}
          {page==='calendar'&&<><div className="action-row"><div><h2 className="content-title">Події на {ukDate(date)}</h2><p className="muted">Ручні події враховуються як фіксований час.</p></div><button className="button primary" onClick={()=>{setEventForm({title:'',start_time:'10:00',end_time:'11:00'});setModal('event')}}><Plus size={18}/>Додати подію</button></div><div className="panel"><div className="panel-heading"><div><h3>Календарні зустрічі</h3><p>Події з локального та підключених календарів</p></div><span className="pill">ЛОКАЛЬНИЙ КАЛЕНДАР</span></div>{events.length?events.map(e=><div className="event-row" key={e.id}><span className="event-time">{e.start_time}–{e.end_time}</span><span className="event-color"/><div><b>{e.title}</b><small>{e.source==='google'?'Google Calendar':e.source==='microsoft'?'Outlook / Teams':'Внесено вручну'}</small></div>{e.source==='manual'&&<button title="Видалити подію" onClick={()=>removeEvent(e.id)}><Trash2 size={17}/></button>}</div>):<div className="empty"><CalendarDays size={36}/><h3>На цей день ще немає подій</h3><p>Додай робочу зустріч або іншу фіксовану подію.</p></div>}</div></>}
          {page==='settings'&&prefs&&<><div className="settings-layout"><div className="panel settings-card"><div className="panel-heading"><div><h3><Sunrise size={19}/> Сон та пробудження</h3><p>Час, у який можна планувати активності</p></div></div><div className="form-grid"><label>Пробудження<input type="time" value={prefs.wake_time} onChange={e=>setPrefs({...prefs,wake_time:e.target.value})}/></label><label>Час сну<input type="time" value={prefs.sleep_time} onChange={e=>setPrefs({...prefs,sleep_time:e.target.value})}/></label></div><label className="stacked">Часовий пояс<input value={prefs.timezone} onChange={e=>setPrefs({...prefs,timezone:e.target.value})}/></label><p className="hint"><Moon size={15}/>Поки що планування відбувається в межах одного календарного дня.</p></div><div className="panel settings-card"><div className="panel-heading"><div><h3><Coffee size={19}/> Прийоми їжі</h3><p>Бажані вікна часу та тривалість</p></div><button className="small-icon" title="Додати прийом їжі" onClick={()=>setPrefs({...prefs,meals:[...prefs.meals,{key:'meal'+Date.now(),title:'Перекус',earliest_start:'15:00',latest_end:'17:00',duration_minutes:30}]})}><Plus size={19}/></button></div><div className="meal-list">{prefs.meals.map((meal,i)=><div className="meal" key={meal.key}><div className="meal-head"><b>{meal.title||'Прийом їжі'}</b><button aria-label="Видалити прийом їжі" onClick={()=>setPrefs({...prefs,meals:prefs.meals.filter((_,n)=>n!==i)})}><Trash2 size={16}/></button></div><div className="meal-fields"><label>Назва<input value={meal.title} onChange={e=>updateMeal(prefs,setPrefs,i,{title:e.target.value})}/></label><label>Від<input type="time" value={meal.earliest_start} onChange={e=>updateMeal(prefs,setPrefs,i,{earliest_start:e.target.value})}/></label><label>До<input type="time" value={meal.latest_end} onChange={e=>updateMeal(prefs,setPrefs,i,{latest_end:e.target.value})}/></label><label>Хв<select value={meal.duration_minutes} onChange={e=>updateMeal(prefs,setPrefs,i,{duration_minutes:+e.target.value})}>{[15,30,45,60,75,90].map(n=><option key={n}>{n}</option>)}</select></label></div></div>)}</div></div></div><div className="settings-save"><button className="button primary" disabled={busy} onClick={saveSettings}><Check size={18}/>Зберегти налаштування</button></div></>}
        </>}
        <footer>Day Builder <span>v0.4 · Preview before apply</span><span>Зроблено з турботою про ваш час</span></footer>
      </section>
    </main>
    {proposal&&<div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setProposal(null)}}>
      <div role="dialog" aria-modal="true" aria-label="Попередній перегляд нового розкладу" className="modal preview-modal">
        <div className="modal-heading"><div><span className="eyebrow">ПЛАН · {proposal.on_date}</span><h2>Підтвердити новий розклад?</h2><p>План залишиться незмінним до підтвердження.</p></div><button className="close" onClick={()=>setProposal(null)}><X size={20}/></button></div>
        <div className="modal-content" style={{maxHeight:'55vh',overflowY:'auto'}}>
          {proposal.warnings.length>0&&<div className="warning-box"><b>⚠ Попередження</b>{proposal.warnings.map((w,i)=><p key={i}>{w}</p>)}</div>}
          <h3>Зміни: {proposal.changes.length}</h3>
          {proposal.changes.map((c,i)=><div key={i} className="preview-change"><b>{c.title}</b><small>{c.before?`${minuteLabel(c.before[0])}–${minuteLabel(c.before[1])}`:'—'} → {c.after?`${minuteLabel(c.after[0])}–${minuteLabel(c.after[1])}`:'—'}</small></div>)}
          <h3>Запропонований розклад</h3>
          {proposal.blocks.map((b,i)=><div className="preview-change" key={i}><span><b>{minuteLabel(b.start_min)}–{minuteLabel(b.end_min)}</b> {b.title}</span><small>{b.kind}</small></div>)}
        </div>
        <div className="modal-footer"><button className="button outlined" onClick={()=>setProposal(null)}>Скасувати</button><button className="button primary" disabled={busy} onClick={applyProposal}>{busy?'Зберігаємо…':'✓ Застосувати план'}</button></div>
      </div>
    </div>}
    {modal&&<div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setModal(null)}}><div role="dialog" aria-modal="true" aria-label={modal==='activity'?'Налаштувати активність':'Додати подію'} className="modal"><div className="modal-heading"><div><span className="eyebrow">DAY BUILDER</span><h2>{modal==='activity'?(editing?'Редагувати активність':'Нова активність'):'Нова подія'}</h2><p>{modal==='activity'?'Підберемо для неї найкращий час.':'Цей проміжок буде зайнятий у розкладі.'}</p></div><button className="close" aria-label="Закрити" onClick={()=>setModal(null)}><X size={21}/></button></div>{modal==='activity'?<div className="modal-content"><label className="stacked">Назва активності<input autoFocus placeholder="Наприклад, вивчити англійську" maxLength={160} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label className="stacked">Опис<textarea rows={2} placeholder="Необов’язково" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><div className="form-grid"><label>Категорія<select value={form.category} onChange={e=>setForm({...form,category:e.target.value as Category})}>{Object.entries(catInfo).map(([k,v])=><option value={k} key={k}>{v.name}</option>)}</select></label><label>Тривалість (хв)<select value={form.duration_minutes} onChange={e=>setForm({...form,duration_minutes:+e.target.value})}>{Array.from({length:32},(_,i)=>(i+1)*15).map(n=><option key={n} value={n}>{n} хв</option>)}</select></label><label>Починаючи з<input type="time" value={form.earliest_start} onChange={e=>setForm({...form,earliest_start:e.target.value})}/></label><label>Завершити до<input type="time" value={form.latest_end} onChange={e=>setForm({...form,latest_end:e.target.value})}/></label><label>Повторення<select value={form.recurrence} onChange={e=>setForm({...form,recurrence:e.target.value as Activity['recurrence']})}><option value="daily">Щодня</option><option value="weekdays">Будні</option><option value="weekends">Вихідні</option><option value="once">Разово</option></select></label><label>Пріоритет<select value={form.priority} onChange={e=>setForm({...form,priority:+e.target.value})}>{[1,2,3,4,5].map(n=><option value={n} key={n}>{n} — {n===5?'Найвищий':n===1?'Низький':'Звичайний'}</option>)}</select></label>{form.recurrence==='once'&&<label>Дата<input type="date" value={form.target_date||date} onChange={e=>setForm({...form,target_date:e.target.value})}/></label>}</div><label className="switch-line"><input type="checkbox" checked={form.required} onChange={e=>setForm({...form,required:e.target.checked})}/><span><b>Обов’язкова активність</b><small>Має бути запланована, якщо це можливо</small></span></label><label className="switch-line"><input type="checkbox" checked={form.enabled} onChange={e=>setForm({...form,enabled:e.target.checked})}/><span><b>Активна</b><small>Додавати до відповідних днів</small></span></label></div>:<div className="modal-content"><label className="stacked">Назва події<input autoFocus placeholder="Наприклад, робоча зустріч" value={eventForm.title} onChange={e=>setEventForm({...eventForm,title:e.target.value})}/></label><div className="form-grid"><label>Початок<input type="time" value={eventForm.start_time} onChange={e=>setEventForm({...eventForm,start_time:e.target.value})}/></label><label>Завершення<input type="time" value={eventForm.end_time} onChange={e=>setEventForm({...eventForm,end_time:e.target.value})}/></label></div><p className="hint">Дата: {ukDate(date)}. Зустрічі автоматично не переносяться.</p></div>}<div className="modal-footer"><button className="button outlined" onClick={()=>setModal(null)}>Скасувати</button><button className="button primary" disabled={busy} onClick={modal==='activity'?saveActivity:saveEvent}><Check size={17}/>{busy?'Зберігаємо...':'Зберегти'}</button></div></div></div>}
  </div>
}
function updateMeal(prefs: Preferences,setPrefs:(v: Preferences)=>void,i: number,patch: Partial<Meal>){setPrefs({...prefs,meals:prefs.meals.map((meal,n)=>n===i?{...meal,...patch}:meal)})}
function Stat({icon,tone,title,value,info}:{icon:ReactNode;tone:string;title:string;value:string;info:string}){return <div className="stat"><div className={'stat-icon '+tone}>{icon}</div><span>{title}</span><strong>{value}</strong><small>{info}</small></div>}
function Timeline({blocks,onToggle,compact=false}:{blocks:Block[];onToggle:(b:Block)=>void;compact?:boolean}){
  if(!blocks.length)return <div className="empty timeline-empty"><AlarmClock size={32}/><h3>Тут з’явиться твій розклад</h3><p>Побудуй план дня — і ми розставимо активності по годинах.</p></div>
  return <div className={'timeline '+(compact?'compact':'')}>{blocks.slice(0,compact?6:undefined).map(b=><div className={'timeline-item '+(b.status==='done'?'finished':'')} key={b.id}><div className="timeline-time">{minuteLabel(b.start_min)}<small>{minuteLabel(b.end_min)}</small></div><div className="timeline-rail"><span className={'timeline-dot '+(b.kind==='event'?'blue':b.kind==='meal'?'green':catInfo[b.category]?.tone||'violet')}/></div><div className="timeline-content"><div className="timeline-title"><strong>{b.title}</strong><div className="block-meta"><span className={'chip '+(b.kind==='event'?'blue':b.kind==='meal'?'green':catInfo[b.category]?.tone||'violet')}>{b.kind==='event'?'Зустріч':b.kind==='meal'?'Харчування':catInfo[b.category]?.name||'Активність'}</span>{b.kind==='activity'&&<button className={'done-action '+(b.status==='done'?'checked':'')} title={b.status==='done'?'Повернути в план':'Позначити виконаною'} onClick={()=>onToggle(b)}>{b.status==='done'?<CheckCheck size={16}/>:<Check size={16}/>}</button>}</div></div><div className="timeline-detail"><Clock size={13}/>{b.end_min-b.start_min} хв<span className="detail-dot">·</span>{b.explanation}</div></div></div>)}{compact&&blocks.length>6&&<p className="extra-blocks">І ще {blocks.length-6} активностей у розкладі</p>}</div>
}
export default App
