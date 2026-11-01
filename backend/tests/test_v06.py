from datetime import date, timedelta


def activity(title='План', recurrence='once', target='2026-10-12'):
    return {'title': title, 'description': '', 'category': 'study', 'duration_minutes': 60,
            'priority': 3, 'required': True, 'earliest_start': '08:00',
            'latest_end': '23:00', 'recurrence': recurrence, 'target_date': target if recurrence == 'once' else None,
            'enabled': True}


def test_week_seven_days_and_once_correct(client):
    assert client.post('/api/activities', json=activity()).status_code == 201
    r=client.get('/api/week/2026-10-13')
    assert r.status_code == 200, r.text
    week=r.json()
    assert week['monday']=='2026-10-12'
    assert len(week['days'])==7
    assert [d['date'] for d in week['days']] == [(date(2026,10,12)+timedelta(days=i)).isoformat() for i in range(7)]
    included=[d['date'] for d in week['days'] if any(b['title']=='План' for b in d['blocks'])]
    assert included == ['2026-10-12']
    assert client.get('/api/plans/2026-10-12').json() is None  # reading preview doesn't save


def test_week_selected_dates_only_and_preserve_locked_meeting(client):
    assert client.post('/api/activities', json=activity('Daily', 'daily')).status_code==201
    assert client.post('/api/events', json={'title':'Google imported simulation','on_date':'2026-10-13','start_time':'08:00','end_time':'09:00'}).status_code==201
    week=client.get('/api/week/2026-10-13').json()
    chosen={day['date']:day['revision'] for day in week['days'] if day['date'] in ('2026-10-12','2026-10-13')}
    saved=client.post('/api/week/apply',json={'monday':week['monday'],'revisions':chosen})
    assert saved.status_code==200, saved.text
    assert saved.json()['count']==2
    assert client.get('/api/plans/2026-10-14').json() is None
    second=client.get('/api/plans/2026-10-13').json()
    meetings=[b for b in second['blocks'] if b['kind']=='event']
    assert len(meetings)==1 and meetings[0]['start_min']==480
    for b in second['blocks']:
        if b['kind']!='event': assert not(b['start_min']<540 and b['end_min']>480)


def test_week_revision_race_aborts_all(client):
    assert client.post('/api/activities',json=activity('Every', 'daily')).status_code==201
    w=client.get('/api/week/2026-10-12').json()
    revisions={day['date']:day['revision'] for day in w['days'][:2]}
    assert client.post('/api/events',json={'title':'late appointment','on_date':'2026-10-13','start_time':'13:00','end_time':'14:00'}).status_code==201
    result=client.post('/api/week/apply',json={'monday':w['monday'],'revisions':revisions})
    assert result.status_code==409
    assert client.get('/api/plans/2026-10-12').json() is None
    assert client.get('/api/plans/2026-10-13').json() is None


def test_week_reject_outside_week_and_non_monday(client):
    w=client.get('/api/week/2026-10-12').json()
    revisions={w['days'][0]['date']:w['days'][0]['revision']}
    assert client.post('/api/week/apply', json={'monday':'2026-10-13','revisions':revisions}).status_code==422
    assert client.post('/api/week/apply', json={'monday':w['monday'],'revisions':{'2026-10-20':'a'*64}}).status_code==422
    assert client.post('/api/week/apply', json={'monday':w['monday'],'revisions':{'2026-10-12':'not a token'}}).status_code==422


def test_week_apply_preserves_done_and_manual_locked_blocks(client):
    client.post('/api/activities',json=activity('Recurring','daily'))
    w=client.get('/api/week/2026-10-12').json()
    assert client.post('/api/week/apply',json={'monday':w['monday'],'revisions':{w['days'][0]['date']:w['days'][0]['revision']}}).status_code==200
    p=client.get('/api/plans/2026-10-12').json()
    block=next(b for b in p['blocks'] if b['kind']=='activity')
    assert client.patch(f"/api/plans/blocks/{block['id']}",json={'status':'done'}).status_code==200
    w2=client.get('/api/week/2026-10-12').json()
    assert client.post('/api/week/apply',json={'monday':w2['monday'],'revisions':{w2['days'][0]['date']:w2['days'][0]['revision']}}).status_code==200
    p2=client.get('/api/plans/2026-10-12').json()
    assert sum(b['status']=='done' for b in p2['blocks'])==1


def test_analytics_empty_days_not_automatic_failures(client):
    r=client.get('/api/insights?end_date=2026-10-12&days=7')
    assert r.status_code==200
    d=r.json()
    assert d['planned_days']==0 and d['totals']['completion_percent'] is None
    assert len(d['daily'])==7 and all(not x['has_plan'] for x in d['daily'])


def test_analytics_counts_done_skipped_minutes_and_focus(client):
    client.post('/api/activities',json=activity('work','daily'))
    result=client.post('/api/plans/preview',json={'on_date':'2026-10-12'}).json()
    p=client.post('/api/plans/apply',json={'on_date':'2026-10-12','revision':result['revision']}).json()
    block=next(b for b in p['blocks'] if b['kind']=='activity')
    client.patch(f"/api/plans/blocks/{block['id']}",json={'status':'done'})
    client.post('/api/focus',json={'on_date':'2026-10-12','title':'work','category':'study','minutes':25})
    client.put('/api/reflections/2026-10-12',json={'mood':4,'energy':3,'note':'ok'})
    d=client.get('/api/insights?end_date=2026-10-12&days=7').json()
    assert d['planned_days']==1 and d['totals']['done']==1
    assert d['totals']['completion_percent']==100
    assert d['totals']['focus_minutes']==25
    assert d['recorded_reflections']==1 and d['recorded_focus_sessions']==1
    assert d['category_minutes']['study']==60
    assert client.get('/api/insights?end_date=2026-10-12&days=8').status_code==422


def test_focus_records_and_deletion(client):
    payload={'on_date':'2026-10-12','title':'Focus','category':'work','minutes':30}
    created=client.post('/api/focus',json=payload)
    assert created.status_code==201
    i=created.json()['id']
    assert client.get('/api/focus?on_date=2026-10-12').json()[0]['minutes']==30
    assert client.post('/api/focus',json={**payload,'minutes':0}).status_code==422
    assert client.post('/api/focus',json={**payload,'minutes':181}).status_code==422
    assert client.delete(f'/api/focus/{i}').status_code==204
    assert client.delete(f'/api/focus/{i}').status_code==404
    assert client.get('/api/focus?on_date=2026-10-12').json()==[]


def test_reflection_create_edit_validation_and_no_exposure_of_tokens(client):
    path='/api/reflections/2026-10-12'
    assert client.get(path).json() is None
    assert client.put(path,json={'mood':6,'energy':3,'note':'bad'}).status_code==422
    assert client.put(path,json={'mood':5,'energy':2,'note':'nice'}).status_code==200
    assert client.put(path,json={'mood':3,'energy':4,'note':'changed'}).status_code==200
    assert client.get(path).json()=={'on_date':'2026-10-12','mood':3,'energy':4,'note':'changed'}


def test_analysis_categories_and_missing_plans(client):
    client.post('/api/activities',json=activity('Once'))
    w=client.get('/api/week/2026-10-12').json()
    d=w['days'][0]
    client.post('/api/week/apply',json={'monday':w['monday'],'revisions':{d['date']:d['revision']}})
    a=client.get('/api/insights?end_date=2026-10-15&days=7').json()
    assert a['planned_days']==1
    assert a['totals']['done']==0
    assert a['totals']['pending']==1
    assert a['totals']['completion_percent']==0
