// No-build standalone UI. Runs without Node/npm, React, or an external connection.
const categories={work:['Робота','💼','blue'],study:['Навчання','📚','violet'],health:['Здоров’я','💚','green'],personal:['Особисте','⭐','orange'],leisure:['Відпочинок','🌿','pink']};
const labels={dashboard:['Твій день — у твоїх руках ✨','Сплануй важливе та залиш час для себе.'],day:['Мій день','Твій реалістичний розклад.'],activities:['Мої активності','Звички й завдання, які формують твій день.'],calendar:['Календар подій','Фіксовані події, що не можуть пересуватися.'],settings:['Мій ритм дня','Ранок, вечір, прийоми їжі.'],week:['Мій тиждень','Перегляд і підтвердження планів на сім днів.'],analytics:['Аналітика','Тільки факти зі збережених розкладів.'],focus:['Режим фокусу','Працюй без відволікань і відстежуй час.'],inbox:['Inbox і підзавдання','Швидко записуй, структуруй і плануй задачі.'],goals:['Цілі','Довгострокові результати та прогрес.'],habits:['Звички','Щоденне виконання без зайвого тиску.'],templates:['Шаблони дня','Повторне використання власних розкладів.']};
let date=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Kyiv',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
let page=new URLSearchParams(location.search).has('calendar')?'calendar':'dashboard', activities=[],events=[],connections=[],prefs=null,plan=null,toast='',error='',edited=null,stale=false;
let oauthMsg=new URLSearchParams(location.search).get('calendar');
let diagnostics=[], editHistory={undo_available:false,redo_available:false,entries:[]}, reminderEnabled=localStorage.getItem('daybuilder-reminders')==='1';
let weekData=null,weekSelection=new Set(),insightsData=null,insightsRange=7,reflectionData=null,focusLog=[],extraLoading=false;
let notificationLead=Number(localStorage.getItem('daybuilder-reminder-lead')||15);
let focusTimer=(()=>{try{return JSON.parse(localStorage.getItem('daybuilder-focus-timer')||'null')}catch{return null}})();
let focusBusy=false;
let inboxItems=[],goalsData=[],goalProgress=[],habitsData=[],templatesData=[],policies=[],reminderState=[];
let theme=localStorage.getItem('daybuilder-theme')||'light';
let calendarView=localStorage.getItem('daybuilder-calendar-view')||'month',calendarRange=[];
document.documentElement.dataset.theme=theme;

if(oauthMsg){window.history.replaceState({},'',location.pathname);}

const safe=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=(n)=>`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;
const readable=(d)=>new Intl.DateTimeFormat('uk-UA',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z'));
const el=(selector)=>document.querySelector(selector);
const request=async(path,method='GET',data)=>{
 let response;
 try {response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});}
 catch{throw new Error('Сервер недоступний. Запустіть Day Builder (FastAPI).')}
 if(!response.ok){const out=await response.json().catch(()=>({}));let detail=out.detail||'Сервер повернув помилку '+response.status;if(Array.isArray(detail))detail=detail.map(x=>x.msg).join('; ');throw Error(detail)}
 return response.status===204?null:response.json();
};
const notify=(msg,bad=false)=>{toast=bad?'':msg;error=bad?msg:'';render()};
async function load(){try{[activities,events,prefs,plan,connections,diagnostics,editHistory]=await Promise.all([request('/activities'),request('/events?on_date='+date),request('/settings'),request('/plans/'+date),request('/integrations'),request('/integrations/diagnostics'),request('/plans/'+date+'/history')]);localStorage.setItem('daybuilder-offline-state',JSON.stringify({activities,events,prefs,plan,connections}));if(oauthMsg){toast=oauthMsg==='connected'?'Календар підключено! Натисніть «Синхронізувати».':'Не вдалося завершити підключення календаря.';oauthMsg=null}}catch(e){
    error='Офлайн: '+e.message+' (доступний лише останній збережений перегляд).';
    try{const cached=JSON.parse(localStorage.getItem('daybuilder-offline-state')||'null');if(cached){activities=cached.activities;events=cached.events;prefs=cached.prefs;plan=cached.plan;connections=cached.connections;}}catch{}
   }render();await loadExtra()}
function nav(){const items=[['dashboard','▦','Огляд'],['day','▤','Мій день'],['activities','☷','Активності'],['calendar','▦','Календар'],['inbox','☷','Inbox'],['goals','◎','Цілі'],['habits','✧','Звички'],['templates','▧','Шаблони'],['week','▦','Тиждень'],['focus','◷','Фокус'],['analytics','▥','Аналітика'],['settings','⚙','Налаштування']];return `<aside class="sidebar"><div class="brand"><div class="brand-icon">◈</div><div><b>day<span>builder</span></b><small>YOUR PERSONAL PLANNER</small></div></div><div class="nav-caption">РОБОЧИЙ ПРОСТІР</div><nav>${items.map(([id,icon,name])=>`<button class="nav-item ${page===id?'active':''}" data-page="${id}" title="${name}"><span style="font-size:19px">${icon}</span> ${name}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="tip-art">✦</div><b>Маленькі кроки — великі результати</b><p>Плануй реалістично. Виконуй важливе. Відпочивай без провини.</p><span>DAY BUILDER · v1.0 BETA</span></div></aside>`}
function head(){return `<header class="topbar"><div class="breadcrumbs">Day Builder › <strong>${labels[page][0]}</strong></div><div class="top-actions"><span class="local-pill"><span class="online-dot"></span>Локальний режим</span><button class="theme-switch" data-theme title="Змінити тему" aria-label="Змінити тему">${theme==='dark'?'☀ Світла':'☾ Темна'}</button><span class="avatar">DB</span></div></header><section class="body"><div class="heading"><div><div class="eyebrow">✦ ТВОЄ ПЛАНУВАННЯ, ТВОЇ ПРАВИЛА</div><h1>${labels[page][0]}</h1><p>${labels[page][1]}</p></div><div class="date-picker"><button id="prev" aria-label="Попередній день">‹</button><input type="date" id="date" value="${date}"/><button id="next" aria-label="Наступний день">›</button></div></div>${error?`<div class="notice danger" role="alert">${safe(error)} <button data-close>×</button></div>`:''}${toast?`<div class="notice success" role="status">${safe(toast)} <button data-close>×</button></div>`:''}${plan?.calendar_stale?'<div class="notice amber" role="status">📅 Змінилися активності або календарні події. Поточний план потребує оновлення. <button data-build>Перебудувати день</button></div>':''}${stale?'<div class="notice amber">Вхідні дані змінилися. Натисніть «Побудувати день» для оновлення розкладу.</div>':''}`}
function stats(){const blocks=plan?.blocks||[],done=blocks.filter(b=>b.kind==='activity'&&b.status==='done').length,total=blocks.filter(b=>b.kind==='activity').length,busy=blocks.reduce((s,b)=>s+b.end_min-b.start_min,0);const duration=prefs?toMin(prefs.sleep_time)-toMin(prefs.wake_time):930;
return `<div class="stat-grid">${[['✓','Виконано справ',done+' / '+total,'активностей за день','violet'],['◷','Заплановано',Math.floor(busy/60)+' год '+busy%60+' хв','разом із зустрічами','blue'],['✦','Зайнятість дня',Math.round(busy/Math.max(duration,1)*100)+'%','від часу неспання','orange'],['☕','Для себе',blocks.filter(b=>b.category==='leisure').length,'приємних активностей','green']].map(([icon,label,value,caption,tone])=>`<div class="stat"><div class="stat-icon ${tone}">${icon}</div><span>${label}</span><strong>${value}</strong><small>${caption}</small></div>`).join('')}</div>`}
function timeline(compact=false){
 const blocks=plan?.blocks||[];
 if(!blocks.length)return '<div class="empty timeline-empty"><h3>Тут з’явиться твій розклад</h3><p>Додай активності й натисни «Побудувати день».</p></div>';
 return `<div class="timeline ${compact?'compact-timeline':'editable-timeline'}">${blocks.slice(0,compact?6:undefined).map((b,i)=>{
  const c=categories[b.category]||categories.personal;
  const kind=b.kind==='meal'?'Харчування':b.kind==='event'?'Зустріч':b.kind==='custom'?'Власний блок':c[0];
  const editable=b.kind!=='event';
  const draggable=!compact&&editable&&!b.is_locked&&b.status==='pending';
  const controls=!compact ? `<div class="day-block-controls">
    ${editable?`<button data-editblock="${b.id}" title="Редагувати назву, час або тривалість" aria-label="Редагувати ${safe(b.title)}">✎</button>
    <button data-lockblock="${b.id}" title="${b.is_locked?'Розблокувати час':'Закріпити час'}" aria-label="Закріпити час">${b.is_locked?'🔒':'🔓'}</button>
    ${b.status==='pending'&&!b.is_locked?`<button data-shift="-1" data-block="${b.id}" title="Поміняти місцями з попереднім блоком">↑</button><button data-shift="1" data-block="${b.id}" title="Поміняти місцями з наступним блоком">↓</button>`:''}
    ${b.kind==='custom'?`<button data-deleteblock="${b.id}" title="Прибрати власний блок">🗑</button>`:''}`:'<span class="fixed-tag" title="Календарні зустрічі не можна пересувати">🔒 Фіксовано</span>'}
    ${b.kind==='activity'||b.kind==='custom'?`<button data-skip="${b.id}" title="${b.status==='skipped'?'Повернути до виконання':'Пропустити справу'}">${b.status==='skipped'?'↩ Повернути':'⏭ Пропустити'}</button>${b.status==='pending'&&!b.is_locked?`<button data-tomorrow="${b.id}" title="Створити справу на наступний день">→ Завтра</button>`:''}`:''}
   </div>`:'';
  return `<div class="timeline-item ${b.status==='done'?'finished':''} ${b.status==='skipped'?'skipped':''} ${draggable?'drag-ready':''}" ${draggable?'draggable="true"':''} data-plan-row="${b.id}">
   <div class="timeline-time">${time(b.start_min)}<small>${time(b.end_min)}</small></div>
   <div class="timeline-rail"><span class="timeline-dot ${b.kind==='meal'?'green':b.kind==='event'?'blue':c[2]}"></span></div>
   <div class="timeline-content"><div class="timeline-title"><strong>${safe(b.title)} ${b.is_locked&&editable?'<span title="Закріплено">🔒</span>':''}</strong>
   <div class="block-meta"><span class="chip ${c[2]}">${kind}</span>${b.status==='skipped'?'<span class="chip optional">Пропущено</span>':''}${(b.kind==='activity'||b.kind==='custom')?`<button class="done-action ${b.status==='done'?'checked':''}" data-done="${b.id}" title="${b.status==='done'?'Повернути до виконання':'Позначити виконаним'}" aria-label="Виконання справи">${b.status==='done'?'✓':'○'}</button>`:''}</div></div>
   <div class="timeline-detail">◷ ${b.end_min-b.start_min} хв · ${safe(b.explanation)}</div>${controls}</div></div>`;
 }).join('')}${compact&&blocks.length>6?`<p class="extra-blocks">Ще ${blocks.length-6} блоків у розкладі</p>`:''}</div>`;
}
function dashboard(){const next=plan?.blocks.find(b=>b.kind==='activity'&&b.status==='pending');return `<div class="hero"><div class="hero-text"><div class="hero-chip">✦ ВАШ РОЗУМНИЙ ПОМІЧНИК</div><h2>Зроби сьогодні<br/><span>саме те, що важливо.</span></h2><p>Найкращий час для справ, зустрічей і відпочинку — без перевантаження.</p><button class="button white" data-build>✦ ${plan?'Перебудувати':'Побудувати'} мій день →</button></div><div class="hero-graphic"><div class="orbit orbit-a"></div><div class="orbit orbit-b"></div><div class="hero-center" style="font-size:55px">☀</div><div class="orbit-note note-one">✓ Все під контролем</div><div class="orbit-note note-two">♡ Баланс щодня</div></div></div>${stats()}<div class="split"><section class="panel"><div class="panel-heading"><div><h3>План на сьогодні</h3><p>${readable(date)}</p></div><button class="link" data-page="day">Увесь день →</button></div>${timeline(true)}</section><section class="panel side-panel"><div class="panel-heading"><div><h3>У фокусі</h3><p>Що робити далі</p></div><span class="pill">МІЙ ПЛАН</span></div><div class="focus"><div class="focus-icon">✦</div><span class="subtle">НАСТУПНА АКТИВНІСТЬ</span><h3>${next?safe(next.title):plan?'Чудово, всі справи зроблено!':'План дня ще порожній'}</h3><p>${next?time(next.start_min)+' – '+time(next.end_min):'Додай завдання та створи розклад.'}</p>${next?`<button class="button primary" data-done="${next.id}">✓ Позначити виконаним</button>`:''}</div><div class="quick-actions"><h4>Швидкі дії</h4><button data-addactivity>＋ Додати активність →</button><button data-addevent>▦ Додати зустріч →</button></div></section></div>`}
function day(){
 const n=plan?.blocks.length||0;
 return `<div class="action-row"><div><h2 class="content-title">${readable(date)}</h2><p class="muted">${n} блоків · перетягуй незакріплені справи мишкою або використовуй ↑ ↓; для точного часу натискай ✎</p></div>
 <div class="day-toolbar"><button class="button outlined" data-undo ${!editHistory.undo_available?'disabled':''} title="Скасувати останню зміну">↶ Скасувати</button>
 <button class="button outlined" data-redo ${!editHistory.redo_available?'disabled':''} title="Повторити скасовану зміну">↷ Повторити</button>
 <button class="button outlined" data-export ${!plan?'disabled':''} title="Завантажити iCalendar">↓ .ics</button>
 <button class="button outlined" data-template-create ${!plan?'disabled':''}>▧ Шаблон</button><button class="button outlined" data-reminders>${reminderEnabled?'🔔 Нагадування':'🔕 Нагадування'}</button>
 <button class="button outlined" data-custom ${!plan?'disabled':''}>＋ Свій блок</button>
 <button class="button primary" data-build>⟳ Побудувати день</button></div></div>
 ${plan?.warnings?.length?`<div class="warning-box"><div class="warning-heading">⚠ Потрібна твоя увага</div>${plan.warnings.map(w=>`<p>${safe(w)}</p>`).join('')}</div>`:''}
 <div class="panel timeline-panel"><div class="panel-heading"><div><h3>Розклад дня</h3><p>Редагуй справи без зміни подій Google Calendar. Закріплені блоки зберігають час під час перепланування.</p></div><span class="pill">${plan?'ЗБЕРЕЖЕНО':'НЕ СТВОРЕНО'}</span></div>${timeline()}</div><section class="panel reminder-controls"><h3>🔔 Відкладання нагадувань</h3><p class="hint">Вкладка має бути відкритою. Керуй нагадуваннями поточних незавершених справ.</p>${(plan?.blocks||[]).filter(b=>b.kind==='activity'&&b.status==='pending').map(b=>`<div class="smart-row"><strong>${safe(b.title)} · ${time(b.start_min)}</strong><div class="smart-buttons"><button data-snooze="${b.id}">Відкласти на 10 хв</button><button data-dismiss-reminder="${b.id}">Не нагадувати</button></div></div>`).join('')||'<p class="muted">Немає очікуваних справ.</p>'}</section>${reflectionWidget()}`
}
function activityCards(){return `<div class="action-row"><div><h2 class="content-title">Всі активності <span class="count">${activities.length}</span></h2><p class="muted">Обов’язкові та гнучкі завдання.</p></div><button class="button primary" data-addactivity>＋ Нова активність</button></div><div class="activities-grid">${activities.length?activities.map(a=>{const c=categories[a.category];return `<div class="activity-card"><div class="activity-top"><span class="category-icon ${c[2]}">${c[1]}</span><div class="activity-actions"><button data-policy="${a.id}" title="Розумні правила: дедлайн, дні, підготовка">⚙</button><button data-edit="${a.id}" title="Редагувати">✎</button><button data-delete="${a.id}" title="Видалити">🗑</button></div></div><h3>${safe(a.title)}</h3><p class="activity-desc">${safe(a.description||'Без опису')}</p><div class="tags"><span class="chip ${c[2]}">${c[0]}</span><span class="chip ${a.required?'required':'optional'}">${a.required?'Обов’язкова':'За бажанням'}</span><span class="chip optional">${a.recurrence==='once'?'Разово: '+safe(a.target_date||'дата не вказана'):a.recurrence==='daily'?'Щодня':a.recurrence==='weekdays'?'Будні':a.recurrence==='weekends'?'Вихідні':'За правилами'}</span></div><div class="activity-footer"><span>◷ ${a.duration_minutes} хв</span><span>${a.earliest_start}–${a.latest_end}</span></div></div>`}).join(''):`<div class="empty panel wide"><h3>Поки немає активностей</h3><p>Додайте навчання, спорт чи особисті справи.</p><button class="button primary" data-addactivity>＋ Перша активність</button></div>`}</div>`}
function calendar(){
 const providers=[['google','Google Calendar','Google'],['microsoft','Outlook / Teams','Microsoft']];
 const integrations=`<div class="panel integration-panel"><div class="panel-heading"><div><h3>Підключені календарі</h3><p>Тільки читання — зустрічі залишаються у вихідних календарях.</p></div><span class="pill">OAUTH 2.0</span></div><div class="integrations">${providers.map(([id,title,vendor])=>{
 const c=connections.find(c=>c.provider===id)||{};
 return `<div class="integration-row"><div class="integration-info"><span class="integration-logo">${id==='google'?'📅':'📘'}</span><div><b>${title}</b><small>${c.connected?(c.last_error?'Помилка останньої синхронізації · спробуйте вручну':c.last_synced_at?'Підключено · оновлено '+new Date(c.last_synced_at).toLocaleString('uk-UA'):'Підключено · потрібна перша синхронізація')+(c.auto_sync_enabled?' · автооновлення увімкнено':' · тільки вручну'):c.configured?'Готово до підключення':'Не налаштовані OAuth credentials'}</small></div></div><div class="integration-actions">${c.connected?`<button class="button primary" data-sync="${id}">⟳ Синхронізувати</button><button class="button outlined" data-disconnect="${id}">Відключити</button>`:c.configured?`<button class="button primary" data-connect="${id}">Підключити</button>`:`<span class="muted integration-hint">Див. docs/calendar-setup.md</span>`}</div></div>`
 }).join('')}</div><p class="hint">Синхронізація імпортує події за період: 2 дні до вибраної дати та 14 днів після. Можна увімкнути фонове оновлення через DAYBUILDER_AUTO_SYNC=1; після зміни подій переглянь та підтвердь новий план.</p></div>`;
 const wizard=`<div class="panel" style="padding:22px;margin-bottom:18px"><div class="panel-heading"><div><h3>🔐 Майстер підключення календаря</h3><p>Безпечні локальні налаштування OAuth. Ключі зберігай лише у файлі .env.</p></div><button class="button outlined" data-checksetup>✓ Перевірити</button></div><div class="setup-grid">${diagnostics.map(d=>`<div class="setup-item"><b>${d.provider==='google'?'Google Calendar':'Microsoft Outlook / Teams'}</b><p class="muted">${d.connected?'✅ Авторизовано':d.configured?'🟡 Ключі налаштовані, потрібна авторизація':'⚪ Потрібні OAuth credentials'}</p><p>Redirect URI:</p><code>${safe(d.redirect_uri)}</code>${d.missing_variables.length?`<p>У .env відсутні: <b>${d.missing_variables.map(safe).join(', ')}</b></p>`:''}<p>${d.provider==='google'?'<a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer">Google Cloud Console ↗</a>':'<a href="https://entra.microsoft.com/" target="_blank" rel="noopener noreferrer">Microsoft Entra ↗</a>'}</p></div>`).join('')}</div><p class="hint">1. Створи OAuth Web application у відповідній консолі. 2. Додай redirect URI. 3. Заповни .env і перезапусти сервер. 4. Натисни «Підключити», погодься на доступ до календаря тільки для читання. 5. Синхронізуй зустрічі. Microsoft 365 може вимагати схвалення адміністратора.</p><p class="hint">Детальні інструкції: docs/calendar-setup.md. Ця перевірка не звертається до акаунтів постачальників без авторизації.</p></div>`;
 return `<div class="action-row"><div><h2 class="content-title">Події на ${readable(date)}</h2><p class="muted">Зустрічі враховуються під час побудови дня.</p></div><button class="button primary" data-addevent>＋ Додати подію</button></div>${calendarBoard()}${integrations}${wizard}<div class="panel"><div class="panel-heading"><div><h3>Фіксовані події</h3><p>Ручні, Google Calendar, Outlook / Teams</p></div><span class="pill">${events.length} ПОДІЙ</span></div>${events.length?events.map(e=>`<div class="event-row"><span class="event-time">${e.start_time}–${e.end_time}</span><span class="event-color"></span><div><b>${safe(e.title)}</b><small>${e.source==='google'?'Google Calendar':e.source==='microsoft'?'Outlook / Teams':'Локальна подія'}</small></div>${e.source==='manual'?`<button data-editevent="${e.id}" title="Редагувати">✎</button><button data-delevent="${e.id}" title="Видалити">🗑</button>`:'<span class="source-lock" title="Керується зовнішнім календарем">🔒</span>'}</div>`).join(''):'<div class="empty"><h3>Немає подій на цей день</h3><p>Додайте зустріч вручну або синхронізуйте календар.</p></div>'}</div>`
}
function settings(){if(!prefs)return '<div class="empty">Налаштування недоступні</div>';return `<div class="settings-layout"><div class="panel settings-card"><div class="panel-heading"><div><h3>☀ Сон і пробудження</h3><p>Активності плануються між цими годинами.</p></div></div><div class="form-grid"><label>Пробудження<input id="wake" type="time" value="${prefs.wake_time}"></label><label>Час сну<input id="sleep" type="time" value="${prefs.sleep_time}"></label></div><label class="stacked">Часовий пояс<input id="zone" value="${safe(prefs.timezone)}"></label><div class="form-grid"> <label>Найпродуктивніше з<input type="time" id="peak-start" value="${prefs.energy_peak_start||'09:00'}"></label><label>До<input type="time" id="peak-end" value="${prefs.energy_peak_end||'12:00'}"></label></div><p class="hint">◷ Планування в межах одного календарного дня.</p></div><div class="panel settings-card"><div class="panel-heading"><div><h3>☕ Прийоми їжі</h3><p>Часові вікна для прийомів їжі</p></div><button class="small-icon" data-addmeal title="Додати прийом їжі">＋</button></div><div class="meal-list">${prefs.meals.map((m,i)=>`<div class="meal"><div class="meal-head"><b>${safe(m.title)}</b><button data-removemeal="${i}">🗑</button></div><div class="meal-fields"><label>Назва<input data-meal="${i}" data-field="title" value="${safe(m.title)}"></label><label>Від<input type="time" data-meal="${i}" data-field="earliest_start" value="${m.earliest_start}"></label><label>До<input type="time" data-meal="${i}" data-field="latest_end" value="${m.latest_end}"></label><label>Хв<select data-meal="${i}" data-field="duration_minutes">${[15,30,45,60,75,90].map(v=>`<option value="${v}" ${m.duration_minutes===v?'selected':''}>${v}</option>`).join('')}</select></label></div></div>`).join('')}</div></div></div><div class="panel settings-card" style="margin:18px 0"><h3>🔔 Нагадування</h3><p class="muted">Локальні повідомлення працюють, доки вкладка відкрита.</p><label class="stacked">За скільки хвилин попередити?<select id="lead-minutes">${[5,10,15,20,30,60].map(n=>`<option value="${n}" ${notificationLead===n?'selected':''}>${n} хв</option>`).join('')}</select></label><button class="button outlined" data-template-create ${!plan?'disabled':''}>▧ Шаблон</button><button class="button outlined" data-reminders>${reminderEnabled?'🔔 Вимкнути нагадування':'🔕 Увімкнути нагадування'}</button></div><div class="settings-save"><button class="button outlined" data-backup>↓ Резервна копія .zip</button> <button class="button primary" data-savesettings>✓ Зберегти налаштування</button></div>`}
function toMin(value){const [h,m]=value.split(':').map(Number);return h*60+m}
function render(){el('#app').innerHTML=`<div class="shell">${nav()}<main class="main">${head()}${({dashboard,day,activities:activityCards,calendar,settings,week:weekPage,analytics:analyticsPage,focus:focusPage,inbox:inboxPage,goals:goalsPage,habits:habitsPage,templates:templatesPage}[page])()}<footer>Day Builder <span>v1.0 beta · Smart Planning / Goals / Habits / Backup</span><span>Твій час важливий</span></footer></section></main></div>`}
function modal(content,kind='activity'){const overlay=document.createElement('div');overlay.className='modal-backdrop';overlay.id='overlay';overlay.innerHTML=`<div class="modal" role="dialog" aria-modal="true"><div class="modal-heading"><div><span class="eyebrow">DAY BUILDER</span><h2>${kind==='event'?'Нова календарна подія':kind==='block'?'Блок розкладу':'Активність'}</h2><p>Налаштуйте деталі нижче.</p></div><button class="close" data-cancel>×</button></div><form id="entry"><div class="modal-content">${content}</div><div class="modal-footer"><button type="button" class="button outlined" data-cancel>Скасувати</button><button class="button primary" type="submit">✓ Зберегти</button></div></form></div>`;overlay.addEventListener('mousedown',e=>{if(e.target===overlay)overlay.remove()});document.body.append(overlay);return overlay}
function field(label,name,value,type='text',more=''){return `<label class="stacked">${label}<input name="${name}" type="${type}" value="${safe(value)}" ${more}></label>`}
function activityForm(id){const a=activities.find(x=>x.id===id)||{title:'',description:'',category:'personal',duration_minutes:60,priority:3,required:true,earliest_start:'08:00',latest_end:'23:00',recurrence:'daily',target_date:date,enabled:true};edited=id||null;
const m=modal(`${field('Назва активності','title',a.title,'text','required maxlength="160"')}${field('Опис','description',a.description)}<div class="form-grid"><label>Категорія<select name="category">${Object.entries(categories).map(([id,v])=>`<option value="${id}" ${a.category===id?'selected':''}>${v[0]}</option>`).join('')}</select></label><label>Тривалість<select name="duration_minutes">${Array.from({length:32},(_,i)=>(i+1)*15).map(n=>`<option value="${n}" ${a.duration_minutes===n?'selected':''}>${n} хв</option>`).join('')}</select></label>${field('Не раніше','earliest_start',a.earliest_start,'time')}${field('До','latest_end',a.latest_end,'time')}<label>Періодичність<select name="recurrence">${[['daily','Щодня'],['weekdays','Будні'],['weekends','Вихідні'],['custom','За правилами'],['once','Разово']].map(([value,label])=>`<option value="${value}" ${a.recurrence===value?'selected':''}>${label}</option>`).join('')}</select></label><label>Пріоритет<select name="priority">${[1,2,3,4,5].map(n=>`<option ${a.priority===n?'selected':''}>${n}</option>`).join('')}</select></label><label class="stacked once-date-field" data-once-date ${a.recurrence==='once'?'':'hidden'}>Дата виконання (лише один день)<input name="target_date" type="date" value="${safe(a.target_date||date)}" ${a.recurrence==='once'?'required':''}></label></div><p class="hint" data-recurrence-note>${a.recurrence==='once'?'Ця активність з’явиться тільки '+safe(a.target_date||date)+'.':'Повторювана активність додаватиметься до кожного відповідного дня.'}</p><label class="switch-line"><input type="checkbox" name="required" ${a.required?'checked':''}><span><b>Обов’язкова активність</b></span></label><label class="switch-line"><input type="checkbox" name="enabled" ${a.enabled?'checked':''}><span><b>Активна</b></span></label>`);
const recurrenceField=m.querySelector('[name="recurrence"]');
const dateField=m.querySelector('[data-once-date]');
const onceDateInput=m.querySelector('[name="target_date"]');
const updateRecurrence=()=>{
 const once=recurrenceField.value==='once';
 dateField.hidden=!once;
 onceDateInput.required=once;
 m.querySelector('[data-recurrence-note]').textContent=once
  ?'Буде заплановано лише на '+onceDateInput.value+'.'
  :'Буде додано до всіх днів за вибраною періодичністю. Дата не використовується.';
};
recurrenceField.addEventListener('change',updateRecurrence);
onceDateInput.addEventListener('change',updateRecurrence);
updateRecurrence();
m.querySelector('form').addEventListener('submit',async(e)=>{e.preventDefault();const f=new FormData(e.currentTarget);const record={title:f.get('title'),description:f.get('description'),category:f.get('category'),duration_minutes:+f.get('duration_minutes'),priority:+f.get('priority'),required:f.has('required'),enabled:f.has('enabled'),earliest_start:f.get('earliest_start'),latest_end:f.get('latest_end'),recurrence:f.get('recurrence'),target_date:f.get('recurrence')==='once'?f.get('target_date'):null};try{await request('/activities'+(edited?'/'+edited:''),edited?'PUT':'POST',record);m.remove();stale=true;await load();notify('Активність збережена. Перебудуйте день.')}catch(e){window.alert(e.message)}})}
function eventForm(id){const ev=events.find(x=>x.id===id);const m=modal(`${field('Назва зустрічі','title',ev?.title||'','text','required')}${field('Початок','start_time',ev?.start_time||'10:00','time')}${field('Кінець','end_time',ev?.end_time||'11:00','time')}<p class="hint">Локальна подія на ${readable(date)}. Підключені Google-зустрічі редагуйте у Google Calendar.</p>`,'event');m.querySelector('form').addEventListener('submit',async(e)=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await request('/events'+(ev?'/'+ev.id:''),ev?'PUT':'POST',{title:f.get('title'),on_date:date,start_time:f.get('start_time'),end_time:f.get('end_time')});m.remove();stale=true;await load();notify('Подію збережено. Перебудуйте день.')}catch(e){window.alert(e.message)}})}
async function build(){
 try{
  const selectedDate=date;
  const proposal=await request('/plans/preview','POST',{on_date:selectedDate});
  const panel=document.createElement('div');
  panel.className='modal-backdrop';panel.id='overlay';
  const formatRange=r=>r?`${time(r[0])}–${time(r[1])}`:'—';
  panel.innerHTML=`<div class="modal preview-modal" role="dialog" aria-modal="true" aria-label="Попередній перегляд розкладу"><div class="modal-heading"><div><span class="eyebrow">ПРОПОЗИЦІЯ · ${safe(selectedDate)}</span><h2>Підтвердити новий план?</h2><p>Зміни не зберігаються, доки ти не натиснеш «Застосувати».</p></div><button class="close" data-cancel>×</button></div><div class="modal-content" style="max-height:58vh;overflow:auto">${proposal.warnings.length?`<div class="warning-box"><b>⚠ Попередження</b>${proposal.warnings.map(w=>`<p>${safe(w)}</p>`).join('')}</div>`:''}${proposal.changes.length?`<h3>Що зміниться</h3>${proposal.changes.map(c=>`<div class="preview-change"><b>${safe(c.title)}</b><small>${safe(c.kind==='added'?'Додано':c.kind==='removed'?'Прибрано':'Перенесено')}: ${formatRange(c.before)} → ${formatRange(c.after)}</small></div>`).join('')}`:'<p class="muted">Розміщення активностей не зміниться.</p>'}<h3>Запропонований розклад · ${proposal.blocks.length} блоків</h3>${proposal.blocks.map(b=>`<div class="preview-change"><span><strong>${time(b.start_min)}–${time(b.end_min)}</strong> ${safe(b.title)}</span><small>${safe(b.kind==='event'?'Календар':b.kind==='meal'?'Харчування':'Активність')}</small></div>`).join('')||'<p>Немає активностей.</p>'}</div><div class="modal-footer"><button class="button outlined" data-cancel>Скасувати</button><button class="button primary" id="apply-proposal">✓ Застосувати план</button></div></div>`;
  panel.addEventListener('mousedown',e=>{if(e.target===panel)panel.remove()});
  document.body.append(panel);
  panel.querySelector('#apply-proposal').addEventListener('click',async e=>{
   const button=e.currentTarget;button.disabled=true;button.textContent='Зберігаємо…';
   try{
    plan=await request('/plans/apply','POST',{on_date:selectedDate,revision:proposal.revision});
    const savedWarnings=plan.warnings.length;panel.remove();stale=false;await load();notify(savedWarnings?'План збережено з попередженнями':'Новий розклад підтверджено й збережено!');
   }catch(err){panel.remove();notify(err.message+' Повтори попередній перегляд.',true)}
  });
 }catch(e){notify(e.message,true)}
}
// v0.5: local manual day editor with optimistic server-side conflict protection.
const clockMinutes=t=>{const parts=String(t).split(':').map(Number);return parts[0]*60+parts[1]};
async function updateTimeline(path,method,payload,message){
 try{plan=await request(path,method,payload); await load(); notify(message||'Розклад оновлено та збережено.');}
 catch(err){notify(err.message,true)}
}
function blockForm(block=null){
 if(!plan){notify('Спочатку побудуйте день.',true);return;}
 if(block&&(block.kind==='event'||block.status==='done')){notify('Зустрічі Google Calendar та вже виконані справи не можна пересувати.',true);return;}
 const fresh=!block;
 const b=block||{title:'',category:'personal',start_min:Math.max(480,clockMinutes(prefs?.wake_time||'08:00')),end_min:540,is_locked:true};
 const end=Math.max(b.end_min,b.start_min+5);
 const content=`${field('Назва блоку','title',b.title,'text','required maxlength="160"')}
 <div class="form-grid">${field('Початок','start_time',time(b.start_min),'time','required step="300"')}
 ${field('Завершення','end_time',time(end),'time','required step="300"')}
 <label>Категорія<select name="category">${Object.entries(categories).map(([value,c])=>`<option value="${value}" ${b.category===value?'selected':''}>${safe(c[0])}</option>`).join('')}</select></label>
 <label>Закріпити час<select name="is_locked"><option value="true" ${b.is_locked?'selected':''}>Так — не рухати автоматично</option><option value="false" ${!b.is_locked?'selected':''}>Ні — дозволити перепланування</option></select></label></div>
 <p class="hint">Підтримується крок 5 хв. Редагування не змінює вихідну регулярну активність, тільки блок цього дня. Програма перевірить конфлікти та час неспання.</p>`;
 const m=modal(content,'block');
 m.querySelector('form').addEventListener('submit',async e=>{
  e.preventDefault();
  const f=new FormData(e.currentTarget),payload={title:f.get('title').trim(),category:f.get('category'),start_min:clockMinutes(f.get('start_time')),end_min:clockMinutes(f.get('end_time')),is_locked:f.get('is_locked')==='true'};
  const path=fresh?'/plans/blocks':'/plans/blocks/'+block.id+'/edit';
  if(fresh)payload.on_date=date;
  try{plan=await request(path,fresh?'POST':'PUT',payload);m.remove();await load();notify(fresh?'Власний блок додано':'Час і деталі блоку збережено')}
  catch(err){window.alert(err.message)}
 });
}
async function swapBlocks(source,target){
 if(!plan||source===target)return;
 await updateTimeline('/plans/reorder','POST',{on_date:date,block_id:source,target_id:target},'Блоки переставлено. Зміна збережена.');
}
async function markStatus(id,status){
 try{await request('/plans/blocks/'+id,'PATCH',{status});await load();notify(status==='done'?'Справу виконано':status==='skipped'?'Справу пропущено':'Справу повернуто до плану')}
 catch(err){notify(err.message,true)}
}
// Drag-and-drop is desktop-friendly; arrow buttons handle touch and keyboard use.
let draggedBlock=null;
document.addEventListener('dragstart',e=>{const r=e.target.closest('[data-plan-row].drag-ready');if(!r)return;draggedBlock=Number(r.dataset.planRow);e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(draggedBlock));r.classList.add('dragging')});
document.addEventListener('dragover',e=>{const r=e.target.closest('[data-plan-row].drag-ready');if(!r||draggedBlock===null)return;e.preventDefault();e.dataTransfer.dropEffect='move';r.classList.add('drag-over')});
document.addEventListener('dragleave',e=>{const r=e.target.closest('[data-plan-row]');if(r)r.classList.remove('drag-over')});
document.addEventListener('drop',async e=>{const r=e.target.closest('[data-plan-row].drag-ready');if(!r||draggedBlock===null)return;e.preventDefault();const from=draggedBlock;draggedBlock=null;document.querySelectorAll('.drag-over,.dragging').forEach(x=>x.classList.remove('drag-over','dragging'));await swapBlocks(from,Number(r.dataset.planRow))});
document.addEventListener('dragend',()=>{draggedBlock=null;document.querySelectorAll('.drag-over,.dragging').forEach(x=>x.classList.remove('drag-over','dragging'))});
async function toggleReminders(){
 if(!reminderEnabled){
  if(!('Notification' in window)){notify('Браузер не підтримує повідомлення.',true);return;}
  const permission=await Notification.requestPermission();
  if(permission!=='granted'){notify('Щоб увімкнути нагадування, дозволь повідомлення для localhost у браузері.',true);return;}
 }
 reminderEnabled=!reminderEnabled;localStorage.setItem('daybuilder-reminders',reminderEnabled?'1':'0');
 notify(reminderEnabled?'Нагадування активні, доки відкрита сторінка Day Builder.':'Нагадування вимкнено.');
}
async function reminderTick(){
 if(!reminderEnabled||!plan||Notification.permission!=='granted')return;
 let controls=[];
 try{controls=await request('/reminders/'+date)}catch{return}

 const zone=prefs?.timezone||'Europe/Kyiv';let currentDate,nowMin;
 try{const items=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date());
 const val=t=>items.find(p=>p.type===t)?.value||'';
 currentDate=val('year')+'-'+val('month')+'-'+val('day'); nowMin=Number(val('hour'))*60+Number(val('minute'));
 }catch{return}
 if(currentDate!==date)return;
 for(const b of plan.blocks){if(b.status!=='pending')continue;
  const control=controls.find(x=>x.block_id===b.id);
  if(control?.dismissed)continue;
  if(control?.snooze_until && new Date(control.snooze_until)>new Date())continue;
  if(control?.snooze_until && Math.abs(Date.now()-new Date(control.snooze_until).getTime())<=30000){
    const key=`db-snooze:${date}:${b.id}:${control.snooze_until}`;
    if(!localStorage.getItem(key)){localStorage.setItem(key,'1');new Notification('Day Builder · відкладене нагадування',{body:b.title,tag:key});}
  }
  for(const [offset,label] of [[notificationLead,`Через ${notificationLead} хв`],[0,'Починається зараз']]){
   if(nowMin<b.start_min-offset||nowMin>b.start_min-offset+1)continue;
   const key=`db-remind:${date}:${b.id}:${b.start_min}:${offset}`;
   if(localStorage.getItem(key))continue;
   localStorage.setItem(key,'1');
   new Notification('Day Builder · '+label,{body:`${b.title} · ${time(b.start_min)}–${time(b.end_min)}`,tag:key});
  }
 }
}
setInterval(reminderTick,30000);
document.addEventListener('click',async(e)=>{const b=e.target.closest('button');if(!b)return;
if(b.hasAttribute('data-page')){page=b.dataset.page;toast=error='';render();await loadExtra();return;}
if(b.hasAttribute('data-tomorrow')){if(confirm('Перенести справу на завтра? У поточному дні вона стане пропущеною, а завтра з’явиться нова разова активність.'))await runSmart('/plans/blocks/'+b.dataset.tomorrow+'/tomorrow','POST');return;}
if(b.hasAttribute('data-snooze')){await runSmart('/reminders/'+date+'/'+b.dataset.snooze,'PUT',{minutes:10,dismiss:false});return;}
if(b.hasAttribute('data-dismiss-reminder')){await runSmart('/reminders/'+date+'/'+b.dataset.dismissReminder,'PUT',{minutes:0,dismiss:true});return;}
if(b.hasAttribute('data-calview')){calendarView=b.dataset.calview;localStorage.setItem('daybuilder-calendar-view',calendarView);render();return;}
if(b.hasAttribute('data-select-date')){date=b.dataset.selectDate;await load();return;}
if(b.hasAttribute('data-theme')){theme=theme==='light'?'dark':'light';document.documentElement.dataset.theme=theme;localStorage.setItem('daybuilder-theme',theme);render();return;}
if(b.hasAttribute('data-policy')){policyForm(Number(b.dataset.policy));return;}
if(b.hasAttribute('data-inbox-add')){inboxForm();return;}
if(b.hasAttribute('data-inbox-edit')){inboxForm(Number(b.dataset.inboxEdit));return;}
if(b.hasAttribute('data-inbox-done')){await runSmart('/inbox/'+b.dataset.inboxDone+'/state?state=done','PATCH');return;}
if(b.hasAttribute('data-inbox-delete')){if(confirm('Видалити завдання?'))await runSmart('/inbox/'+b.dataset.inboxDelete,'DELETE');return;}
if(b.hasAttribute('data-inbox-schedule')){await runSmart('/inbox/'+b.dataset.inboxSchedule+'/schedule','POST',{on_date:date,category:'personal',required:true});return;}
if(b.hasAttribute('data-goal-add')){goalForm();return;}
if(b.hasAttribute('data-goal-edit')){goalForm(Number(b.dataset.goalEdit));return;}
if(b.hasAttribute('data-goal-delete')){if(confirm('Видалити ціль?'))await runSmart('/goals/'+b.dataset.goalDelete,'DELETE');return;}
if(b.hasAttribute('data-habit-add')){habitForm();return;}
if(b.hasAttribute('data-habit-edit')){habitForm(Number(b.dataset.habitEdit));return;}
if(b.hasAttribute('data-habit-delete')){if(confirm('Видалити звичку?'))await runSmart('/habits/'+b.dataset.habitDelete,'DELETE');return;}
if(b.hasAttribute('data-habit-check')){const h=habitsData.find(x=>x.id===Number(b.dataset.habitCheck));if(h)await runSmart('/habits/'+h.id+'/check?on_date='+date+'&checked='+!h.checked,'PUT');return;}
if(b.hasAttribute('data-template-create')){await createTemplate();return;}
if(b.hasAttribute('data-template-apply')){if(confirm('Додати блоки шаблону до '+date+'?'))await runSmart('/templates/'+b.dataset.templateApply+'/apply?on_date='+date,'POST');return;}
if(b.hasAttribute('data-template-delete')){if(confirm('Видалити шаблон?'))await runSmart('/templates/'+b.dataset.templateDelete,'DELETE');return;}
if(b.hasAttribute('data-backup')){location.href='/api/backup';return;}
if(b.hasAttribute('data-day-replan')){await build();return;}

if(b.id==='prev'||b.id==='next'){const d=new Date(date+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+(b.id==='next'?1:-1));date=d.toISOString().slice(0,10);stale=false;await load()}
if(b.hasAttribute('data-close')){toast=error='';render()}
if(b.hasAttribute('data-build'))await build();
if(b.hasAttribute('data-editblock')){const block=plan?.blocks.find(x=>x.id===Number(b.dataset.editblock));if(block)blockForm(block);return;}
if(b.hasAttribute('data-custom')){blockForm();return;}
if(b.hasAttribute('data-lockblock')){const block=plan?.blocks.find(x=>x.id===Number(b.dataset.lockblock));if(block)await updateTimeline('/plans/blocks/'+block.id+'/lock','PATCH',{is_locked:!block.is_locked},block.is_locked?'Час розблоковано':'Час закріплено');return;}
if(b.hasAttribute('data-shift')){const rows=[...(plan?.blocks||[])].sort((a,z)=>a.start_min-z.start_min);const index=rows.findIndex(x=>x.id===Number(b.dataset.block));const other=rows[index+Number(b.dataset.shift)];if(other)await swapBlocks(rows[index].id,other.id);return;}
if(b.hasAttribute('data-deleteblock')){if(confirm('Видалити цей власний блок з плану?'))await updateTimeline('/plans/blocks/'+b.dataset.deleteblock+'/custom','DELETE',undefined,'Власний блок видалено');return;}
if(b.hasAttribute('data-skip')){const block=plan?.blocks.find(x=>x.id===Number(b.dataset.skip));if(block)await markStatus(block.id,block.status==='skipped'?'pending':'skipped');return;}
if(b.hasAttribute('data-undo')||b.hasAttribute('data-redo')){const mode=b.hasAttribute('data-undo')?'undo':'redo';await updateTimeline('/plans/'+date+'/'+mode,'POST',{},mode==='undo'?'Останню зміну скасовано':'Зміну повторено');return;}
if(b.hasAttribute('data-export')){if(plan)location.href='/api/plans/'+date+'/export.ics';return;}
if(b.hasAttribute('data-reminders')){await toggleReminders();return;}
if(b.hasAttribute('data-addactivity'))activityForm();
if(b.hasAttribute('data-edit'))activityForm(+b.dataset.edit);
if(b.hasAttribute('data-delete')){if(confirm('Видалити активність?'))try{await request('/activities/'+b.dataset.delete,'DELETE');stale=true;await load();notify('Активність видалено. Перебудуйте день.')}catch(e){notify(e.message,true)}}
if(b.hasAttribute('data-checksetup')){try{diagnostics=await request('/integrations/diagnostics');render();notify('Перевірка локальних OAuth налаштувань завершена.')}catch(err){notify(err.message,true)}return;}
if(b.hasAttribute('data-connect')){location.href='/api/integrations/'+b.dataset.connect+'/start';return;}
if(b.hasAttribute('data-sync')){const provider=b.dataset.sync;b.disabled=true;b.textContent='Синхронізація…';try{const r=await request('/integrations/'+provider+'/sync','POST',{on_date:date});stale=stale||r.change_count>0;await load();notify('Імпортовано '+r.events_imported+' подій. '+(r.change_count?'Змінилися '+r.change_count+' дні — перебудуйте план.':'Нових змін немає.'))}catch(err){notify(err.message,true)}return;}
if(b.hasAttribute('data-disconnect')){if(confirm('Відключити календар і прибрати імпортовані події?'))try{await request('/integrations/'+b.dataset.disconnect,'DELETE');stale=true;await load();notify('Календар відключено. Перебудуйте день.')}catch(err){notify(err.message,true)}return;}
if(b.hasAttribute('data-addevent'))eventForm();
if(b.hasAttribute('data-editevent'))eventForm(+b.dataset.editevent);
if(b.hasAttribute('data-delevent')){if(confirm('Видалити календарну подію?'))try{await request('/events/'+b.dataset.delevent,'DELETE');stale=true;await load();notify('Подію видалено. Перебудуйте день.')}catch(e){notify(e.message,true)}}
if(b.hasAttribute('data-done')){const block=plan?.blocks.find(x=>x.id===+b.dataset.done);if(block)await markStatus(block.id,block.status==='done'?'pending':'done');return;}
if(b.hasAttribute('data-cancel'))el('#overlay')?.remove();
if(b.hasAttribute('data-addmeal')){prefs.meals.push({key:'meal'+Date.now(),title:'Перекус',earliest_start:'15:00',latest_end:'17:00',duration_minutes:30});render()}
if(b.hasAttribute('data-removemeal')){prefs.meals.splice(+b.dataset.removemeal,1);render()}
if(b.hasAttribute('data-weekday')){date=b.dataset.weekday;page='day';stale=false;await load();return;}
if(b.hasAttribute('data-weekapply')){await confirmSelectedWeek();return;}
if(b.hasAttribute('data-weekrefresh')){await loadExtra();return;}
if(b.hasAttribute('data-insights-range')){insightsRange=Number(b.dataset.insightsRange);await loadExtra();return;}
if(b.hasAttribute('data-reflection-save')){await saveReflection();return;}
if(b.hasAttribute('data-focus-start')){beginFocus();return;}
if(b.hasAttribute('data-focus-pause')){pauseFocus();return;}
if(b.hasAttribute('data-focus-resume')){resumeFocus();return;}
if(b.hasAttribute('data-focus-complete')){await finishFocus(true);return;}
if(b.hasAttribute('data-focus-discard')){if(confirm('Скасувати таймер без збереження?')){focusTimer=null;saveFocusState();render()}return;}
if(b.hasAttribute('data-focus-log-delete')){if(confirm('Видалити цей запис фокус-сесії?'))try{await request('/focus/'+b.dataset.focusLogDelete,'DELETE');await loadExtra();notify('Запис видалено.')}catch(err){notify(err.message,true)}return;}
if(b.hasAttribute('data-savesettings')){const selectedLead=el('#lead-minutes');if(selectedLead){notificationLead=Number(selectedLead.value);localStorage.setItem('daybuilder-reminder-lead',String(notificationLead));}prefs.wake_time=el('#wake').value;prefs.sleep_time=el('#sleep').value;prefs.timezone=el('#zone').value;prefs.energy_peak_start=el('#peak-start').value;prefs.energy_peak_end=el('#peak-end').value;try{prefs=await request('/settings','PUT',prefs);stale=true;notify('Налаштування збережено. Перебудуйте день.')}catch(e){notify(e.message,true)}}
});
document.addEventListener('change',async(e)=>{if(e.target.id==='date'&&e.target.value){date=e.target.value;stale=false;await load()}if(e.target.hasAttribute('data-weekselect')){if(e.target.checked)weekSelection.add(e.target.dataset.weekselect);else weekSelection.delete(e.target.dataset.weekselect);render()}if(e.target.hasAttribute('data-meal')){const i=+e.target.dataset.meal,k=e.target.dataset.field;prefs.meals[i][k]=k==='duration_minutes'?+e.target.value:e.target.value}});

// v0.6 — weekly preview, reflections, focus timer, factual statistics.
const plusDays=(d,n)=>{const value=new Date(d+'T12:00:00Z');value.setUTCDate(value.getUTCDate()+n);return value.toISOString().slice(0,10)};
async function loadExtra(){
 extraLoading=true;render();
 try{
  if(page==='week'){
   weekData=await request('/week/'+date);
   weekSelection=new Set(weekData.days.filter(d=>d.needs_update).map(d=>d.date));
  }
  if(page==='analytics')insightsData=await request('/insights?days='+insightsRange+'&end_date='+date);
  if(page==='focus')focusLog=await request('/focus?on_date='+date);
  if(page==='day'){reflectionData=await request('/reflections/'+date);reminderState=await request('/reminders/'+date);}
  if(page==='inbox')inboxItems=await request('/inbox');
  if(page==='calendar'){const start=plusDays(date.slice(0,8)+'01',-((new Date(date.slice(0,8)+'01T12:00:00Z').getUTCDay()+6)%7));calendarRange=await request('/events/range?start='+start+'&days=42');}
  if(page==='goals')[goalsData,goalProgress]=await Promise.all([request('/goals'),request('/goals/progress?on_date='+date)]);
  if(page==='habits')habitsData=await request('/habits?on_date='+date);
  if(page==='templates')templatesData=await request('/templates');
  if(page==='activities')policies=await request('/policies');
 }catch(err){error=err.message}
 extraLoading=false;render();
}
const weekdayTitles=['Понеділок','Вівторок','Середа','Четвер','П’ятниця','Субота','Неділя'];
function weekPage(){
 if(extraLoading&&!weekData)return '<div class="panel empty">Завантаження тижня…</div>';
 if(!weekData)return '<div class="panel empty">Немає даних тижня. <button data-weekrefresh>Оновити</button></div>';
 let selected=weekData.days.filter(d=>weekSelection.has(d.date));
 return `<div class="action-row"><div><h2 class="content-title">Тиждень від ${readable(weekData.monday)}</h2><p class="muted">Попередній перегляд не змінює збережені плани. Дні без вибору не зміняться.</p></div><div class="day-toolbar"><button class="button outlined" data-weekrefresh>⟳ Оновити пропозиції</button><button class="button primary" data-weekapply ${selected.length?'':'disabled'}>✓ Підтвердити ${selected.length} дн.</button></div></div>
 <div class="week-grid">${weekData.days.map((d,i)=>{
  const tasks=d.blocks.filter(b=>b.kind==='activity'),events=d.blocks.filter(b=>b.kind==='event');
  const meals=d.blocks.filter(b=>b.kind==='meal');
  return `<article class="week-card ${d.warnings.length?'week-warning':''}"><header class="week-card-head"><div><small>${weekdayTitles[i]}</small><h3>${readable(d.date)}</h3></div><input type="checkbox" aria-label="Підтвердити план на ${d.date}" data-weekselect="${d.date}" ${weekSelection.has(d.date)?'checked':''} /></header>
  <div class="week-metrics"><span>📌 ${events.length} зустрічей</span><span>☑ ${tasks.length} завдань</span><span>☕ ${meals.length} харчування</span></div>
  <p class="week-hours">${Math.floor(d.planned_minutes/60)} год ${d.planned_minutes%60} хв · заплановано</p>
  ${d.warnings.length?`<div class="week-warnings">⚠ ${d.warnings.length} попереджень${d.warnings.some(x=>x.includes('Не вдалося'))?' · є невміщені справи':''}</div>`:''}
  <div class="week-events">${d.blocks.slice(0,6).map(b=>`<div><span>${time(b.start_min)}</span><b>${safe(b.title)}</b></div>`).join('')||'<p>День вільний</p>'}${d.blocks.length>6?`<small>Ще ${d.blocks.length-6} блоків</small>`:''}</div>
  <button class="button outlined" data-weekday="${d.date}">Відкрити день →</button></article>`
 }).join('')}</div>
 <p class="hint">Підтвердження перевіряє всі вибрані дні та календарні зміни. Якщо дані змінилися після перегляду, жоден вибраний день не буде збережено, доки ти не оновиш пропозиції.</p>`;
}
async function confirmSelectedWeek(){
 const revisions=Object.fromEntries((weekData?.days||[]).filter(d=>weekSelection.has(d.date)).map(d=>[d.date,d.revision]));
 const count=Object.keys(revisions).length;
 if(!count||!confirm(`Зберегти ${count} вибраних днів? Попередні незакріплені блоки цих днів можуть змінитися.`))return;
 try{const r=await request('/week/apply','POST',{monday:weekData.monday,revisions});await load();page='week';await loadExtra();notify(`Збережено ${r.count} днів. Інші плани не змінені.`)}catch(e){notify(e.message,true);await loadExtra()}
}
function analyticsPage(){
 if(!insightsData)return '<div class="panel empty">Завантаження статистики…</div>';
 const a=insightsData,t=a.totals,percent=t.completion_percent,max=Math.max(1,...a.daily.map(d=>d.activity_minutes));
 return `<div class="action-row"><div><h2 class="content-title">Статистика виконання</h2><p class="muted">Враховано лише ${a.planned_days} днів зі збереженим планом. Порожні дні не вважаються пропущеними.</p></div><div class="range-picker">${[7,30,90].map(n=>`<button class="button ${insightsRange===n?'primary':'outlined'}" data-insights-range="${n}">${n} днів</button>`).join('')}</div></div>
 <div class="insights-cards">${[['Виконання',percent===null?'—':percent+'%','Справ зі статусом виконано'],['Виконані',t.done,'Завершених активностей'],['Пропущені',t.skipped,'Не виконані за вибором'],['Фокус',t.focus_minutes+' хв','Записані фокус-сесії'],['Зустрічі',Math.round(t.meeting_minutes/60*10)/10+' год','Календарні події'],['Нотатки',a.recorded_reflections,'Підсумків дня']].map(([title,value,desc])=>`<div class="insights-card"><span>${title}</span><strong>${value}</strong><small>${desc}</small></div>`).join('')}</div>
 <div class="panel"><div class="panel-heading"><div><h3>Навантаження за днями</h3><p>Хвилини активностей у збережених планах</p></div></div><div class="insights-bars">${a.daily.map(d=>`<div class="insight-line"><span>${d.date.slice(5)}</span><div class="bar-track"><div class="bar-fill" style="width:${d.activity_minutes/max*100}%"></div></div><b>${d.has_plan?d.activity_minutes+' хв':'—'}</b>${d.stale?'<small title="Потрібна перебудова">⚠</small>':''}</div>`).join('')}</div></div>
 <div class="panel"><div class="panel-heading"><div><h3>Розподіл часу</h3><p>Категорії, хвилини запланованих активностей і власних блоків</p></div></div>${Object.entries(a.category_minutes).map(([key,value])=>`<div class="category-line"><span>${safe((categories[key]||categories.personal)[0])}</span><b>${value} хв</b></div>`).join('')||'<p class="muted">Поки немає запланованих активностей.</p>'}</div>`;
}
function reflectionWidget(){
 const r=reflectionData||{};
 return `<section class="panel reflection-panel"><div class="panel-heading"><div><h3>✍ Підсумок дня</h3><p>Коротко занотуй свій стан та висновки. Це приватний локальний запис.</p></div></div><div class="form-grid"><label>Настрій<select id="reflection-mood">${[1,2,3,4,5].map(n=>`<option value="${n}" ${r.mood===n?'selected':''}>${n} / 5</option>`).join('')}</select></label><label>Енергія<select id="reflection-energy">${[1,2,3,4,5].map(n=>`<option value="${n}" ${r.energy===n?'selected':''}>${n} / 5</option>`).join('')}</select></label></div><label class="stacked">Що вдалося сьогодні?<textarea id="reflection-note" maxlength="2000" rows="3" placeholder="Короткий підсумок, думки, висновки…">${safe(r.note||'')}</textarea></label><button class="button primary" data-reflection-save>✓ Зберегти підсумок</button></section>`;
}
async function saveReflection(){
 try{const data={mood:Number(el('#reflection-mood').value),energy:Number(el('#reflection-energy').value),note:el('#reflection-note').value};reflectionData=await request('/reflections/'+date,'PUT',data);notify('Підсумок дня збережено.')}catch(e){notify(e.message,true)}
}
function saveFocusState(){if(focusTimer)localStorage.setItem('daybuilder-focus-timer',JSON.stringify(focusTimer));else localStorage.removeItem('daybuilder-focus-timer')}
function focusRemaining(){if(!focusTimer)return 0;return Math.max(0,Math.ceil(focusTimer.remaining-(focusTimer.running?(Date.now()-focusTimer.startedAt)/1000:0)))}
function focusPage(){
 const r=focusRemaining(),min=String(Math.floor(r/60)).padStart(2,'0'),sec=String(r%60).padStart(2,'0');
 let options=(plan?.blocks||[]).filter(b=>b.kind==='activity'&&b.status==='pending');
 return `<div class="panel focus-workspace"><div><span class="eyebrow">✦ ЗОСЕРЕДЖЕННЯ</span><h2>Зараз лише одна справа</h2><p class="muted">Таймер працює у вкладці, а час, який реально відпрацював, можна записати в історію.</p></div>
 <div class="focus-clock" id="focus-clock">${focusTimer?min+':'+sec:'25:00'}</div>
 ${!focusTimer?`<div class="focus-fields"><label>Назва справи<input id="focus-title" list="focus-title-options" placeholder="Наприклад, програмування" value="${safe(options[0]?.title||'')}" maxlength="160"></label><datalist id="focus-title-options">${options.map(b=>`<option value="${safe(b.title)}"></option>`).join('')}</datalist><label>Категорія<select id="focus-category">${Object.entries(categories).map(([key,v])=>`<option value="${key}">${v[0]}</option>`).join('')}</select></label><label>Тривалість<select id="focus-duration">${[5,15,25,45,50,60,90].map(n=>`<option value="${n}" ${n===25?'selected':''}>${n} хв</option>`).join('')}</select></label></div><button class="button primary" data-focus-start>▶ Почати фокус</button>`:
 `<h3>${safe(focusTimer.title)}</h3><p class="muted">Почато на ${readable(focusTimer.on_date)} · ${focusTimer.duration} хв</p><div class="focus-buttons">${focusTimer.running?'<button class="button outlined" data-focus-pause>⏸ Пауза</button>':'<button class="button outlined" data-focus-resume>▶ Продовжити</button>'}<button class="button primary" data-focus-complete>${r===0?'✓ Зберегти сесію':'✓ Завершити й записати час'}</button><button class="button outlined" data-focus-discard>Скинути</button></div>`}
 <p class="hint">Режим фокусу не позначає активність виконаною автоматично. Якщо браузер закрити, стан таймера відновиться з локальних даних, але фонові сповіщення не гарантуються.</p></div>
 <div class="panel"><div class="panel-heading"><div><h3>Журнал фокусу · ${readable(date)}</h3><p>Записані завершені сесії</p></div><span class="pill">${focusLog.reduce((s,f)=>s+f.minutes,0)} ХВ</span></div>${focusLog.length?focusLog.map(f=>`<div class="focus-record"><span>◷ <b>${f.minutes} хв</b> · ${safe(f.title)}</span><button data-focus-log-delete="${f.id}" title="Видалити запис">🗑</button></div>`).join(''):'<p class="muted">Сесій поки немає.</p>'}</div>`;
}
function beginFocus(){const title=(el('#focus-title')?.value||'').trim();if(!title){notify('Введи назву активності.',true);return}const duration=Number(el('#focus-duration').value);focusTimer={title,category:el('#focus-category').value,on_date:date,duration,remaining:duration*60,startedAt:Date.now(),running:true};saveFocusState();render()}
function pauseFocus(){if(!focusTimer)return;focusTimer.remaining=focusRemaining();focusTimer.running=false;saveFocusState();render()}
function resumeFocus(){if(!focusTimer)return;focusTimer.startedAt=Date.now();focusTimer.running=true;saveFocusState();render()}
async function finishFocus(manual){
 if(!focusTimer||focusBusy)return;
 const elapsed=focusTimer.duration*60-focusRemaining();
 const actual=Math.min(180,Math.floor(elapsed/60));
 if(actual<1){if(manual)notify('Для запису фокус-сесії потрібно щонайменше 1 хвилина.',true);return;}
 focusBusy=true;pauseFocus();
 try{await request('/focus','POST',{on_date:focusTimer.on_date,title:focusTimer.title,category:focusTimer.category,minutes:actual});focusTimer=null;saveFocusState();if(page==='focus')await loadExtra();notify(`Збережено ${actual} хв зосередженої роботи.`)}
 catch(e){notify('Не вдалося зберегти сесію: '+e.message,true)}finally{focusBusy=false}
}
setInterval(()=>{
 if(!focusTimer)return;
 const countdown=document.getElementById('focus-clock');const left=focusRemaining();
 if(countdown)countdown.textContent=String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');
 // Only record once after the full timer has run and no manual action is pending.
 if(left===0&&focusTimer.running&&!focusBusy)finishFocus(false);
},1000);

load();
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
// Observe background imports without overwriting user input inside an open form.
setInterval(async()=>{
 if(document.hidden || el('#overlay') || !['calendar','day','dashboard'].includes(page))return;
 try{
  const [nextEvents,nextConnections,nextPlan] = await Promise.all([
   request('/events?on_date='+date),request('/integrations'),request('/plans/'+date)
  ]);
  if(JSON.stringify(events)!==JSON.stringify(nextEvents) ||
     JSON.stringify(connections)!==JSON.stringify(nextConnections) ||
     JSON.stringify(plan)!==JSON.stringify(nextPlan)){
    events=nextEvents;connections=nextConnections;plan=nextPlan;render();
  }
 }catch{/* No disruption when temporarily offline. */}
},60000);

// v1.0 — dedicated smart workspaces and modals, all forms validate in the API.
const chosen=(v,a)=>String(v)===String(a)?'selected':'';
async function runSmart(path,method='GET',body=null){
 try{await request(path,method,body);await load();notify('Збережено успішно.');}
 catch(err){notify(err.message,true)}
}
function inboxPage(){
 const active=inboxItems.filter(t=>t.state!=='archived');
 return `<div class="action-row"><div><h2 class="content-title">Швидкий запис справ</h2><p class="muted">Завдання не потрапить у план без твоєї команди «Запланувати». Підзавдання прив'язуються до батьківської справи.</p></div><button class="button primary" data-inbox-add>＋ Нова справа</button></div>
 <section class="panel smart-list">${active.map(t=>`<div class="smart-row ${t.state==='done'?'muted-row':''}"><div><strong>${t.parent_id?'↳ ':''}${safe(t.title)}</strong><p>${safe(t.notes||'Без опису')} · ${t.duration_minutes} хв · P${t.priority} · ${t.due_date?'до '+t.due_date:'без дедлайну'}${t.state==='done'?' · зроблено':''}</p></div><div class="smart-buttons"><button data-inbox-edit="${t.id}" title="Редагувати">✎</button>${t.state==='inbox'?`<button data-inbox-schedule="${t.id}" title="Створити разову активність на вибраний день">📅 Запланувати</button><button data-inbox-done="${t.id}">✓ Виконано</button>`:''}<button data-inbox-delete="${t.id}" title="Видалити">🗑</button></div></div>`).join('')||'<p class="muted">Inbox порожній. Додай перше завдання.</p>'}</section>`;
}
async function inboxForm(pk=null){
 try{goalsData=await request('/goals');}catch(err){notify(err.message,true);return}
 const t=inboxItems.find(x=>x.id===pk)||{title:'',notes:'',priority:3,duration_minutes:30,due_date:'',parent_id:null,goal_id:null};
 const m=modal(`${field('Назва','title',t.title,'text','required maxlength="160"')}<label class="stacked">Опис<textarea name="notes" rows="2" maxlength="2000">${safe(t.notes)}</textarea></label><div class="form-grid">${field('Дедлайн','due_date',t.due_date||'','date')}<label>Пріоритет<select name="priority">${[1,2,3,4,5].map(i=>`<option value="${i}" ${chosen(i,t.priority)}>${i}</option>`).join('')}</select></label><label>Тривалість<select name="duration_minutes">${[15,30,45,60,90,120,180,240].map(n=>`<option value="${n}" ${chosen(n,t.duration_minutes)}>${n} хв</option>`).join('')}</select></label><label>Підзавдання для<select name="parent_id"><option value="">Незалежне</option>${inboxItems.filter(x=>x.id!==pk).map(x=>`<option value="${x.id}" ${chosen(x.id,t.parent_id)}>${safe(x.title)}</option>`).join('')}</select></label><label>Ціль<select name="goal_id"><option value="">Без цілі</option>${goalsData.map(x=>`<option value="${x.id}" ${chosen(x.id,t.goal_id)}>${safe(x.title)}</option>`).join('')}</select></label></div>`);
 m.querySelector('form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await request('/inbox'+(pk?'/'+pk:''),pk?'PUT':'POST',{title:f.get('title'),notes:f.get('notes'),due_date:f.get('due_date')||null,priority:+f.get('priority'),duration_minutes:+f.get('duration_minutes'),parent_id:f.get('parent_id')?+f.get('parent_id'):null,goal_id:f.get('goal_id')?+f.get('goal_id'):null});m.remove();await load();notify('Справу збережено')}catch(err){alert(err.message)}};
}
function goalsPage(){return `<div class="action-row"><div><h2 class="content-title">Цілі та результати</h2><p class="muted">Встановлюй тижневу норму. Прив’язуй активності через ⚙ у розділі «Активності».</p></div><button class="button primary" data-goal-add>＋ Нова ціль</button></div><section class="smart-grid">${goalsData.map(g=>`<article class="panel smart-card"><div class="smart-card-top"><strong>${safe(g.title)}</strong><div class="smart-buttons"><button data-goal-edit="${g.id}">✎</button><button data-goal-delete="${g.id}">🗑</button></div></div><p>${safe(g.description||'Без опису')}</p><p>🎯 ${g.target_minutes_week} хв на тиждень ${g.due_date?' · дедлайн '+g.due_date:''}</p><p>✓ Виконано: ${goalProgress.find(x=>x.id===g.id)?.done_minutes_week||0} хв на цьому тижні</p>${g.archived?'<span class="chip optional">В архіві</span>':''}</article>`).join('')||'<div class="panel empty">Цілей поки немає</div>'}</section>`}
function goalForm(pk=null){const t=goalsData.find(x=>x.id===pk)||{title:'',description:'',target_minutes_week:120,due_date:null,archived:false};const m=modal(`${field('Назва цілі','title',t.title,'text','required maxlength="160"')}<label class="stacked">Опис<textarea rows="3" name="description" maxlength="2000">${safe(t.description)}</textarea></label><div class="form-grid">${field('Тижнева норма хв','target_minutes_week',t.target_minutes_week,'number','min="15" max="10080"')}${field('Дедлайн','due_date',t.due_date||'','date')}</div><label class="switch-line"><input type="checkbox" name="archived" ${t.archived?'checked':''}> Архівована</label>`);m.querySelector('form').onsubmit=async e=>{e.preventDefault();let f=new FormData(e.currentTarget);try{await request('/goals'+(pk?'/'+pk:''),pk?'PUT':'POST',{title:f.get('title'),description:f.get('description'),target_minutes_week:+f.get('target_minutes_week'),due_date:f.get('due_date')||null,archived:f.has('archived')});m.remove();await load();notify('Ціль збережено')}catch(err){alert(err.message)}};}
function habitsPage(){return `<div class="action-row"><div><h2 class="content-title">Звички на ${readable(date)}</h2><p class="muted">Виконання фіксується тільки на вибрану дату. У звичок є календар активних днів.</p></div><button class="button primary" data-habit-add>＋ Нова звичка</button></div><section class="panel smart-list">${habitsData.map(h=>`<div class="smart-row"><div><strong>${safe(h.title)}</strong><p>${h.minutes} хв · дні: ${h.weekdays.map(x=>['Пн','Вт','Ср','Чт','Пт','Сб','Нд'][x]).join(' ')} · 30 днів: ${h.completed_last_30} виконань</p></div><div class="smart-buttons"><button data-habit-check="${h.id}" ${!h.weekdays.includes(new Date(date+'T12:00:00Z').getUTCDay()===0?6:new Date(date+'T12:00:00Z').getUTCDay()-1)?'disabled':''}>${h.checked?'✓ Виконано':'○ Виконати'}</button><button data-habit-edit="${h.id}">✎</button><button data-habit-delete="${h.id}">🗑</button></div></div>`).join('')||'<p class="muted">Звичок ще немає</p>'}</section>`}
function habitForm(pk=null){const t=habitsData.find(x=>x.id===pk)||{title:'',weekdays:[0,1,2,3,4,5,6],minutes:15,enabled:true,linked_activity_id:null};const m=modal(`${field('Назва звички','title',t.title,'text','required maxlength="160"')}<div class="form-grid">${field('Хвилин','minutes',t.minutes,'number','min="5" max="480"')}<label>Пов’язана активність<select name="linked_activity_id"><option value="">Не прив’язана</option>${activities.map(a=>`<option value="${a.id}" ${chosen(a.id,t.linked_activity_id)}>${safe(a.title)}</option>`).join('')}</select></label></div><div class="weekday-row">${['Пн','Вт','Ср','Чт','Пт','Сб','Нд'].map((v,i)=>`<label><input type="checkbox" name="wd" value="${i}" ${t.weekdays.includes(i)?'checked':''}>${v}</label>`).join('')}</div><label class="switch-line"><input type="checkbox" name="enabled" ${t.enabled?'checked':''}> Активна</label>`);m.querySelector('form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await request('/habits'+(pk?'/'+pk:''),pk?'PUT':'POST',{title:f.get('title'),minutes:+f.get('minutes'),weekdays:f.getAll('wd').map(Number),enabled:f.has('enabled'),linked_activity_id:f.get('linked_activity_id')?+f.get('linked_activity_id'):null});m.remove();await load();notify('Звичку збережено')}catch(err){alert(err.message)}};}
function templatesPage(){return `<div class="action-row"><div><h2 class="content-title">Мої шаблони</h2><p class="muted">Шаблон копіює власні блоки, але не копіює події Google Calendar. Застосування можливе лише без конфліктів.</p></div><button class="button primary" data-template-create>＋ Із плану ${date}</button></div><section class="smart-grid">${templatesData.map(t=>`<article class="panel smart-card"><div class="smart-card-top"><strong>${safe(t.title)}</strong><div class="smart-buttons"><button data-template-delete="${t.id}">🗑</button></div></div><p>${t.blocks_count} блоків у шаблоні</p><button class="button outlined" data-template-apply="${t.id}">＋ На ${date}</button></article>`).join('')||'<div class="panel empty">Шаблонів ще немає</div>'}</section>`}
async function createTemplate(){const title=prompt('Назва шаблону на основі збереженого плану '+date+':');if(!title?.trim())return;await runSmart('/templates','POST',{title:title.trim(),on_date:date});}
async function policyForm(activityId){
 try{[policies,goalsData]=await Promise.all([request('/policies'),request('/goals')]);}catch(e){notify(e.message,true);return}
 const a=activities.find(x=>x.id===activityId);const p=policies.find(x=>x.activity_id===activityId)||{};
 const m=modal(`<h3>${safe(a.title)} · розумні правила</h3><p class="hint">Ці параметри впливають на наступну генерацію плану. Налаштування поточного дня не змінюється автоматично.</p><div class="form-grid">
 ${field('Початок дії','start_date',p.start_date||'','date')}${field('Кінець дії','end_date',p.end_date||'','date')}
 ${field('Дедлайн','due_date',p.due_date||'','date')}${field('Бажаний початок','preferred_start',p.preferred_start||'','time')}
 ${field('Кожні N днів','repeat_every_days',p.repeat_every_days||1,'number','min="1" max="365"')}
 ${field('Рівень енергії 1–5','energy',p.energy||3,'number','min="1" max="5"')}
 ${field('Підготовка хв','prep_minutes',p.prep_minutes||0,'number','min="0" max="180" step="15"')}
 ${field('Дорога хв','travel_minutes',p.travel_minutes||0,'number','min="0" max="180" step="15"')}
 ${field('Перерва після хв','break_after_minutes',p.break_after_minutes||0,'number','min="0" max="120" step="15"')}
 <label>Ціль<select name="goal_id"><option value="">Без цілі</option>${goalsData.map(g=>`<option value="${g.id}" ${chosen(g.id,p.goal_id)}>${safe(g.title)}</option>`).join('')}</select></label>
 </div><p class="hint">Дні тижня (за замовчуванням — періодичність з картки активності):</p><div class="weekday-row">${['Пн','Вт','Ср','Чт','Пт','Сб','Нд'].map((v,i)=>`<label><input name="wd" type="checkbox" value="${i}" ${(p.weekdays||[]).includes(i)?'checked':''}>${v}</label>`).join('')}</div>
 <label class="stacked">Залежить від інших активностей<select name="depends_on" multiple size="${Math.min(4,Math.max(2,activities.length))}">${activities.filter(x=>x.id!==activityId).map(x=>`<option value="${x.id}" ${(p.depends_on||[]).includes(x.id)?'selected':''}>${safe(x.title)}</option>`).join('')}</select></label>`);
 m.querySelector('form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);const payload={due_date:f.get('due_date')||null,start_date:f.get('start_date')||null,end_date:f.get('end_date')||null,preferred_start:f.get('preferred_start')||null,repeat_every_days:+f.get('repeat_every_days'),energy:+f.get('energy'),prep_minutes:+f.get('prep_minutes'),travel_minutes:+f.get('travel_minutes'),break_after_minutes:+f.get('break_after_minutes'),weekdays:f.getAll('wd').map(Number),depends_on:[...m.querySelector('[name=depends_on]').selectedOptions].map(x=>Number(x.value)),goal_id:f.get('goal_id')?+f.get('goal_id'):null};try{await request('/policies/'+activityId,'PUT',payload);m.remove();await load();notify('Правила активності збережено; перебудуйте день.')}catch(err){alert(err.message)}};
}

function calendarBoard(){
 const month=date.slice(0,7),monthStart=month+'-01',firstOffset=(new Date(monthStart+'T12:00:00Z').getUTCDay()+6)%7;
 const start=plusDays(monthStart,-firstOffset);
 let days=calendarView==='week'?Array.from({length:7},(_,i)=>plusDays(date,-((new Date(date+'T12:00:00Z').getUTCDay()+6)%7)+i)):Array.from({length:42},(_,i)=>plusDays(start,i));
 const count=d=>calendarRange.filter(x=>x.on_date===d);
 return `<section class="panel calendar-board"><div class="panel-heading"><div><h3>📅 Огляд календаря</h3><p>Тиждень або місяць. Зовнішні події доступні тільки для перегляду.</p></div><div class="range-picker"><button class="button ${calendarView==='month'?'primary':'outlined'}" data-calview="month">Місяць</button><button class="button ${calendarView==='week'?'primary':'outlined'}" data-calview="week">Тиждень</button></div></div><div class="calendar-grid">${['Пн','Вт','Ср','Чт','Пт','Сб','Нд'].map(x=>`<div class="calendar-weekday">${x}</div>`).join('')}${days.map(d=>`<button class="calendar-tile ${d===date?'selected':''} ${d.slice(0,7)!==month?'offmonth':''}" data-select-date="${d}"><span>${Number(d.slice(-2))}</span>${count(d).slice(0,3).map(e=>`<small title="${safe(e.title)}">${safe(e.start_time)} ${safe(e.title)}</small>`).join('')}${count(d).length>3?`<em>+${count(d).length-3}</em>`:''}</button>`).join('')}</div></section>`;
}
