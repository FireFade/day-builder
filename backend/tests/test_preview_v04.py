"""v0.4: preview never commits changes; stale confirmations are rejected."""


def test_preview_is_readonly_until_explicit_acceptance(client):
    assert client.post('/api/activities', json={
        'title':'Study', 'duration_minutes':60, 'recurrence':'once',
        'target_date':'2026-10-11', 'earliest_start':'10:00', 'latest_end':'13:00'
    }).status_code == 201
    first = client.post('/api/plans/preview', json={'on_date':'2026-10-11'})
    assert first.status_code == 200, first.text
    payload=first.json()
    assert len(payload['revision']) == 64
    assert any(b['title']=='Study' for b in payload['blocks'])
    assert client.get('/api/plans/2026-10-11').json() is None
    assert client.post('/api/plans/preview', json={'on_date':'2026-10-11'}).json()['revision'] == payload['revision']
    result=client.post('/api/plans/apply',json={'on_date':'2026-10-11','revision':payload['revision']})
    assert result.status_code == 200, result.text
    assert client.get('/api/plans/2026-10-11').json()['id'] == result.json()['id']


def test_preview_rejects_changes_from_calendar_before_confirmation(client):
    plan=client.post('/api/plans/generate',json={'on_date':'2026-10-11'}).json()
    proposal=client.post('/api/plans/preview', json={'on_date':'2026-10-11'}).json()
    assert client.post('/api/events',json={
        'title':'Urgent Teams call', 'on_date':'2026-10-11',
        'start_time':'09:00', 'end_time':'11:00'
    }).status_code==201
    rejected=client.post('/api/plans/apply',json={
        'on_date':'2026-10-11','revision':proposal['revision']
    })
    assert rejected.status_code == 409
    assert client.get('/api/plans/2026-10-11').json()['id']==plan['id']
    next_proposal=client.post('/api/plans/preview',json={'on_date':'2026-10-11'}).json()
    assert next_proposal['revision'] != proposal['revision']
    assert client.post('/api/plans/apply',json={
        'on_date':'2026-10-11','revision':next_proposal['revision']
    }).status_code == 200


def test_preview_handles_done_activity_and_warning_without_deleting_original(client):
    activity=client.post('/api/activities',json={
        'title':'Deep work','duration_minutes':60,'recurrence':'once',
        'target_date':'2026-10-11','earliest_start':'08:00','latest_end':'09:00'
    }).json()
    original=client.post('/api/plans/generate',json={'on_date':'2026-10-11'}).json()
    deep = next(b for b in original['blocks'] if b['source_id']==activity['id'])
    assert client.patch('/api/plans/blocks/'+str(deep['id']),json={'status':'done'}).status_code==200
    new=client.post('/api/plans/preview',json={'on_date':'2026-10-11'}).json()
    assert any(b['source_id']==activity['id'] and b['status']=='done' for b in new['blocks'])
    assert client.get('/api/plans/2026-10-11').json()['id']==original['id']
    assert client.post('/api/plans/apply',json={'on_date':'2026-10-11','revision':new['revision']}).status_code==200
    accepted=client.get('/api/plans/2026-10-11').json()
    assert next(b for b in accepted['blocks'] if b['source_id']==activity['id'])['status']=='done'


def test_diagnostics_do_not_expose_credentials(client, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'sensitive-client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'sensitive-secret')
    monkeypatch.delenv('MICROSOFT_CLIENT_SECRET', raising=False)
    response = client.get('/api/integrations/diagnostics')
    assert response.status_code == 200
    data=response.json()
    assert data[0]['configured'] and not data[0]['connected']
    assert data[0]['redirect_uri']=='http://localhost:8000/api/integrations/google/callback'
    assert 'MICROSOFT_CLIENT_SECRET' in data[1]['missing_variables']
    assert 'sensitive-secret' not in response.text
    assert 'sensitive-client-id' not in response.text
    assert client.get('/api/integrations/diagnostics', headers={'origin':'https://evil.example'}).status_code==403


def test_diagnostics_start_rejects_unconfigured(client, monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
    response=client.get('/api/integrations/google/start', follow_redirects=False)
    assert response.status_code == 503
    assert 'GOOGLE_CLIENT_ID' in response.text
