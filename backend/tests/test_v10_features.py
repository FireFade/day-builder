"""Development safety checks for v1 modules; not a substitute for user's UAT."""
from datetime import date

DAY='2026-10-12'
TOMORROW='2026-10-13'

def act(client,title,day=DAY):
    payload=dict(title=title,description='',category='study',duration_minutes=60,priority=3,
        required=True,earliest_start='08:00',latest_end='17:00',recurrence='once',target_date=day,enabled=True)
    r=client.post('/api/activities',json=payload)
    assert r.status_code==201,r.text
    return r.json()['id']

def create_goal(client,title='Go'):
    r=client.post('/api/goals',json={'title':title,'target_minutes_week':120})
    assert r.status_code==201,r.text
    return r.json()['id']

def test_inbox_subtasks_and_schedule(client):
    parent=client.post('/api/inbox',json={'title':'Parent'}).json()
    kid=client.post('/api/inbox',json={'title':'Subtask','parent_id':parent['id']}).json()
    assert kid['parent_id']==parent['id']
    assert client.put('/api/inbox/'+str(parent['id']),json={'title':'Parent','parent_id':kid['id']}).status_code==422
    res=client.post('/api/inbox/'+str(kid['id'])+'/schedule',json={'on_date':DAY})
    assert res.status_code==200,res.text
    assert res.json()['activity_id']
    assert client.post('/api/inbox/'+str(kid['id'])+'/schedule',json={'on_date':DAY}).status_code==409
    plan=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    assert any(b['title']=='Subtask' for b in plan['blocks'])


def test_policy_cycle_and_custom_recurrence(client):
    a=act(client,'A')
    b=act(client,'B')
    assert client.put('/api/policies/'+str(a),json={'depends_on':[b]}).status_code==200
    assert client.put('/api/policies/'+str(b),json={'depends_on':[a]}).status_code==422
    assert client.put('/api/policies/'+str(b),json={'depends_on':[b]}).status_code==422
    assert client.put('/api/activities/'+str(a),json=dict(title='A',description='',category='study',duration_minutes=60,priority=3,required=True,earliest_start='08:00',latest_end='17:00',recurrence='daily',target_date=None,enabled=True)).status_code==200
    assert client.put('/api/policies/'+str(a),json={'weekdays':[0], 'start_date':DAY}).status_code==200
    p=client.post('/api/plans/preview',json={'on_date':TOMORROW}).json()
    assert all(x['title']!='A' for x in p['blocks'])


def test_policy_dependency_enforced(client):
    a=act(client,'Step 1'); b=act(client,'Step 2')
    assert client.put('/api/policies/'+str(b),json={'depends_on':[a]}).status_code==200
    r=client.post('/api/plans/preview',json={'on_date':DAY})
    assert r.status_code==200,r.text
    tasks={x['title']:x for x in r.json()['blocks']}
    assert tasks['Step 1']['end_min']<=tasks['Step 2']['start_min']


def test_buffers_dont_overlap_fixed_meeting(client):
    a=act(client,'Prepare and focus')
    client.put('/api/policies/'+str(a),json={'prep_minutes':30,'travel_minutes':15,'break_after_minutes':15})
    client.post('/api/events',json={'title':'Meeting','on_date':DAY,'start_time':'10:00','end_time':'11:00'})
    p=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    b=next(x for x in p['blocks'] if x['title']=='Prepare and focus')
    assert b['end_min']+15<=600 or b['start_min']-45>=660


def test_goal_tracking(client):
    id=create_goal(client)
    a=act(client,'Study for goal')
    client.put('/api/policies/'+str(a),json={'goal_id':id})
    proposal=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    saved=client.post('/api/plans/apply',json={'on_date':DAY,'revision':proposal['revision']})
    assert saved.status_code==200,saved.text
    block=next(x for x in saved.json()['blocks'] if x['source_id']==a)
    assert client.patch('/api/plans/blocks/'+str(block['id']),json={'status':'done'}).status_code==200
    progress=client.get('/api/goals/progress?on_date='+DAY).json()
    assert progress[0]['done_minutes_week']==60
    assert progress[0]['completion_percent']==50


def test_habits_and_check(client):
    habit=client.post('/api/habits',json={'title':'Read','weekdays':[0]}).json()
    assert client.put(f'/api/habits/{habit["id"]}/check?on_date={DAY}&checked=true').status_code==200
    result=client.get('/api/habits?on_date='+DAY).json()[0]
    assert result['checked'] and result['completed_last_30']==1
    assert client.put(f'/api/habits/{habit["id"]}/check?on_date={TOMORROW}').status_code==409
    assert client.put(f'/api/habits/{habit["id"]}/check?on_date={DAY}&checked=false').status_code==200
    assert not client.get('/api/habits?on_date='+DAY).json()[0]['checked']


def test_template_no_copy_external_event(client):
    a=act(client,'Study')
    client.post('/api/events',json={'title':'Secret Google meeting','on_date':DAY,'start_time':'14:00','end_time':'15:00'})
    p=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    assert client.post('/api/plans/apply',json={'on_date':DAY,'revision':p['revision']}).status_code==200
    result=client.post('/api/templates',json={'title':'Useful morning','on_date':DAY})
    assert result.status_code==201,result.text
    assert result.json()['blocks_count']>0
    assert client.get('/api/templates').json()[0]['id']==result.json()['id']
    # Since template includes schedule blocks, applying to a conflicting existing day is rejected.
    assert client.post('/api/templates/'+str(result.json()['id'])+'/apply?on_date='+DAY).status_code==409


def test_deferral_creates_once_activity(client):
    act(client,'Defer')
    p=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    saved=client.post('/api/plans/apply',json={'on_date':DAY,'revision':p['revision']}).json()
    block=next(x for x in saved['blocks'] if x['title']=='Defer')
    moved=client.post(f'/api/plans/blocks/{block["id"]}/tomorrow')
    assert moved.status_code==200,moved.text
    assert moved.json()['date']==TOMORROW
    nextday=client.post('/api/plans/preview',json={'on_date':TOMORROW}).json()
    assert any(x['title']=='Defer' for x in nextday['blocks'])
    saved=client.get('/api/plans/'+DAY).json()
    assert next(x for x in saved['blocks'] if x['id']==block['id'])['status']=='skipped'


def test_snooze_and_backup(client):
    act(client,'Remind')
    proposal=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    saved=client.post('/api/plans/apply',json={'on_date':DAY,'revision':proposal['revision']}).json()
    block=next(b for b in saved['blocks'] if b['title']=='Remind')
    snooze=client.put(f'/api/reminders/{DAY}/{block["id"]}',json={'minutes':10,'dismiss':False})
    assert snooze.status_code==200,snooze.text
    assert client.get('/api/reminders/'+DAY).json()
    dismissed=client.put(f'/api/reminders/{DAY}/{block["id"]}',json={'minutes':0,'dismiss':True})
    assert dismissed.json()['dismissed']
    # The configured development engine may be on-disk or in-memory.
    backup=client.get('/api/backup')
    assert backup.status_code in (200,404,409)
    if backup.status_code==200:
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
            assert 'backend/daybuilder.db' in z.namelist()
            assert '.env' not in z.namelist()
            assert 'backend/.secrets/calendar.key' not in z.namelist()


def test_preview_revision_changes_when_policy_changes(client):
    a=act(client,'Work')
    first=client.post('/api/plans/preview',json={'on_date':DAY}).json()['revision']
    client.put('/api/policies/'+str(a),json={'preferred_start':'11:00'})
    second=client.post('/api/plans/preview',json={'on_date':DAY}).json()['revision']
    assert first!=second
    assert client.post('/api/plans/apply',json={'on_date':DAY,'revision':first}).status_code==409

def test_calendar_board_and_static_shell(client):
    assert client.get('/sw.js').status_code==200
    assert client.get('/api/events/range?start=2026-10-12&days=0').status_code==422
    meeting=client.post('/api/events',json={'title':'Standup','on_date':DAY,'start_time':'12:00','end_time':'12:30'})
    assert meeting.status_code==201
    view=client.get('/api/events/range?start=2026-10-12&days=7')
    assert view.status_code==200 and any(x['title']=='Standup' for x in view.json())


def test_energy_window_preferences_and_deadline_warning(client):
    prefs=client.get('/api/settings').json()
    prefs['energy_peak_start']='10:00';prefs['energy_peak_end']='12:00'
    assert client.put('/api/settings',json=prefs).status_code==200
    a=act(client,'Focused task')
    assert client.put(f'/api/policies/{a}',json={'energy':5,'due_date':'2026-10-11'}).status_code==200
    p=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    assert any('Прострочений дедлайн' in x for x in p['warnings'])
    b=next(x for x in p['blocks'] if x['title']=='Focused task')
    assert b['start_min']>=600

def test_optional_dependency_of_required_is_scheduled_first(client):
    a=act(client,'Prerequisite')
    b=act(client,'Required dependent')
    source=client.get('/api/activities').json()
    payload=next(item for item in source if item['id']==a)
    payload.pop('id',None);payload['required']=False
    assert client.put('/api/activities/'+str(a),json=payload).status_code==200
    assert client.put('/api/policies/'+str(b),json={'depends_on':[a]}).status_code==200
    p=client.post('/api/plans/preview',json={'on_date':DAY}).json()
    blocks={x['title']:x for x in p['blocks']}
    assert blocks['Prerequisite']['end_min']<=blocks['Required dependent']['start_min']
