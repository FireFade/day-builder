"""v0.5 manual day editing and safety checks."""
DAY = '2026-10-13'

def api(client, route, **kwargs):
    response=client.post(route, **kwargs)
    assert response.status_code < 400, response.text
    return response.json()

def seeded(client):
    client.put('/api/settings', json={'wake_time':'08:00','sleep_time':'23:30','timezone':'Europe/Kyiv','meals':[]})
    for title, first, last in [('A', '09:00','12:00'),('B','09:00','12:00'),('C','09:00','12:00')]:
        assert client.post('/api/activities',json={'title':title,'duration_minutes':30,'earliest_start':first,'latest_end':last,'recurrence':'once','target_date':DAY}).status_code==201
    result=api(client,'/api/plans/generate',json={'on_date':DAY})
    return result

def one(plan,title):
    return next(b for b in plan['blocks'] if b['title']==title)

def edit(client, block, start, end, **changes):
    payload={'title':block['title'], 'category':block['category'], 'start_min':start, 'end_min':end, 'is_locked':True}
    payload.update(changes)
    return client.put(f'/api/plans/blocks/{block["id"]}/edit',json=payload)

def test_move_and_pin_preserved_after_regenerate(client):
    plan=seeded(client)
    block=one(plan,'A')
    edited=edit(client,block,660,690)
    assert edited.status_code==200, edited.text
    changed=one(edited.json(),'A')
    assert changed['is_locked'] and (changed['start_min'],changed['end_min'])==(660,690)
    preview=api(client,'/api/plans/preview',json={'on_date':DAY})
    assert any(b['title']=='A' and b['start_min']==660 for b in preview['blocks'])
    applied=api(client,'/api/plans/apply',json={'on_date':DAY, 'revision':preview['revision']})
    assert one(applied,'A')['start_min']==660
    assert one(applied,'A')['is_locked']

def test_edit_rejects_conflicts_and_outside_wake(client):
    plan=seeded(client)
    a=one(plan,'A')
    taken=one(plan,'B')
    response=edit(client,a,taken['start_min'],taken['end_min'])
    assert response.status_code==409
    assert edit(client,a,100,130).status_code==409
    assert edit(client,a,520,515).status_code==422
    assert one(client.get('/api/plans/'+DAY).json(),'A')['start_min']==a['start_min']

def test_calendar_event_immutable_and_safe(client):
    client.put('/api/settings',json={'wake_time':'08:00','sleep_time':'23:30','timezone':'Europe/Kyiv','meals':[]})
    client.post('/api/events',json={'title':'Meeting','on_date':DAY,'start_time':'10:00','end_time':'11:00'})
    plan=api(client,'/api/plans/generate',json={'on_date':DAY})
    event=one(plan,'Meeting')
    assert edit(client,event,700,760).status_code==409
    assert client.patch('/api/plans/blocks/'+str(event['id'])+'/lock',json={'is_locked':True}).status_code==409
    assert client.patch('/api/plans/blocks/'+str(event['id']),json={'status':'done'}).status_code==400
    assert client.post('/api/plans/blocks',json={'on_date':DAY,'title':'Overlap','category':'study','start_min':615,'end_min':645}).status_code==409

def test_new_manual_events_invalidate_edit(client):
    plan=seeded(client)
    client.post('/api/events',json={'title':'Unplanned meeting','on_date':DAY,'start_time':'15:00','end_time':'16:00'})
    assert edit(client,one(plan,'A'),700,730).status_code==409

def test_custom_block_create_delete_and_history(client):
    seeded(client)
    created=api(client,'/api/plans/blocks',json={'on_date':DAY,'title':'Walk','category':'health','start_min':1020,'end_min':1050,'is_locked':False})
    walk=one(created,'Walk')
    assert walk['kind']=='custom'
    assert len(client.get('/api/plans/'+DAY+'/history').json()['entries'])==1
    removed=client.delete(f'/api/plans/blocks/{walk["id"]}/custom')
    assert removed.status_code==200
    assert all(b['title']!='Walk' for b in removed.json()['blocks'])
    result=api(client,'/api/plans/'+DAY+'/undo')
    assert any(b['title']=='Walk' for b in result['blocks'])
    result=api(client,'/api/plans/'+DAY+'/undo')
    assert all(b['title']!='Walk' for b in result['blocks'])
    result=api(client,'/api/plans/'+DAY+'/redo')
    assert any(b['title']=='Walk' for b in result['blocks'])
    result=api(client,'/api/plans/'+DAY+'/redo')
    assert all(b['title']!='Walk' for b in result['blocks'])
    assert client.post('/api/plans/'+DAY+'/redo').status_code==409

def test_history_invalidated_after_new_edit_and_on_regeneration(client):
    plan=seeded(client)
    a=one(plan,'A')
    assert client.patch(f'/api/plans/blocks/{a["id"]}/lock',json={'is_locked':True}).status_code==200
    api(client,'/api/plans/'+DAY+'/undo')
    assert client.get('/api/plans/'+DAY+'/history').json()['redo_available']
    newest=one(client.get('/api/plans/'+DAY).json(),'A')
    assert client.patch(f'/api/plans/blocks/{newest["id"]}/lock',json={'is_locked':False}).status_code==200
    assert not client.get('/api/plans/'+DAY+'/history').json()['redo_available']
    api(client,'/api/plans/generate',json={'on_date':DAY})
    assert client.get('/api/plans/'+DAY+'/history').json()['entries']==[]

def test_reorder_with_drag_and_restrictions(client):
    plan=seeded(client)
    ordered=[b for b in plan['blocks'] if b['kind']=='activity']
    assert len(ordered)==3
    first, second, third=ordered
    result=api(client,'/api/plans/reorder',json={'on_date':DAY,'block_id':first['id'],'target_id':third['id']})
    new_order=[b['title'] for b in result['blocks'] if b['kind']=='activity']
    assert new_order==[second['title'],third['title'],first['title']]
    mid=next(b for b in result['blocks'] if b['title']==third['title'])
    assert client.patch(f'/api/plans/blocks/{mid["id"]}/lock',json={'is_locked':True}).status_code==200
    ordered=client.get('/api/plans/'+DAY).json()['blocks']
    assert client.post('/api/plans/reorder',json={'on_date':DAY,'block_id':ordered[0]['id'],'target_id':ordered[-1]['id']}).status_code==409

def test_skipped_activity_does_not_reappear_on_preview(client):
    plan=seeded(client)
    b=one(plan,'B')
    assert client.patch(f'/api/plans/blocks/{b["id"]}',json={'status':'skipped'}).status_code==200
    proposal=api(client,'/api/plans/preview',json={'on_date':DAY})
    assert not any(b['title']=='B' for b in proposal['blocks'])

def test_saved_changes_and_history_survive_reloading_endpoint(client):
    plan=seeded(client)
    custom=api(client,'/api/plans/blocks',json={'on_date':DAY,'title':'Journal','start_min':1080,'end_min':1110})
    assert one(client.get('/api/plans/'+DAY).json(),'Journal')['start_min']==1080
    assert api(client,'/api/plans/'+DAY+'/undo')
    assert all(b['title']!='Journal' for b in client.get('/api/plans/'+DAY).json()['blocks'])

def test_export_ics_utc_and_escaping(client):
    seeded(client)
    api(client,'/api/plans/blocks',json={'on_date':DAY,'title':'Reading, practice; notes','start_min':1080,'end_min':1110})
    result=client.get('/api/plans/'+DAY+'/export.ics')
    assert result.status_code==200
    assert 'text/calendar' in result.headers['content-type']
    assert 'DTSTART:20261013T150000Z' in result.text
    assert 'Reading\\, practice\\; notes' in result.text
    assert result.text.count('BEGIN:VEVENT')==4

def test_new_calendar_change_blocks_history(client):
    plan=seeded(client)
    a=one(plan,'A')
    assert client.patch(f'/api/plans/blocks/{a["id"]}/lock',json={'is_locked':True}).status_code==200
    client.post('/api/events',json={'title':'New meeting','on_date':DAY,'start_time':'15:00','end_time':'16:00'})
    assert client.post('/api/plans/'+DAY+'/undo').status_code==409

def test_edit_manual_calendar_marks_plan_stale(client):
    plan=seeded(client)
    result=client.post('/api/events',json={'title':'Manual call','on_date':DAY,'start_time':'15:00','end_time':'16:00'})
    assert result.status_code==201
    event=result.json()
    assert client.get('/api/plans/'+DAY).json()['calendar_stale']
    assert client.put('/api/events/'+str(event['id']),json={'title':'Changed','on_date':DAY,'start_time':'16:00','end_time':'17:00'}).status_code==200
    assert client.delete('/api/events/'+str(event['id'])).status_code==204
    assert client.get('/api/events?on_date='+DAY).json()==[]


def test_stale_plan_rejects_manual_edit_even_without_overlap(client):
    plan=seeded(client)
    old=one(plan,'A')
    client.post('/api/events',json={'title':'New booking','on_date':DAY,'start_time':'19:00','end_time':'20:00'})
    result=edit(client,old,1100,1130)
    assert result.status_code==409


def test_manual_calendar_event_cannot_edit_google(client):
    # Mimic imported read-only Google event using the existing SQLAlchemy test dependency.
    from app.db import get_db
    from app.main import app
    from app.models import CalendarEvent
    with next(iter(app.dependency_overrides[get_db]())) as session:
        session.add(CalendarEvent(title='Imported',on_date=__import__('datetime').date.fromisoformat(DAY),
                                  start_time='14:00',end_time='15:00',source='google',external_key='google:test'))
        session.commit()
    imported=next(e for e in client.get('/api/events?on_date='+DAY).json() if e['source']=='google')
    assert client.put('/api/events/'+str(imported['id']),json={'title':'No','on_date':DAY,'start_time':'15:00','end_time':'16:00'}).status_code==409
    assert client.delete('/api/events/'+str(imported['id'])).status_code==409
