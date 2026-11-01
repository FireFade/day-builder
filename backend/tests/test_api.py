from datetime import date

DAY = '2026-10-12'

def activity(client, title='Програмування', **kwargs):
    data = dict(title=title, duration_minutes=120, earliest_start='09:00', latest_end='18:00', required=True, priority=4)
    data.update(kwargs)
    response = client.post('/api/activities', json=data)
    assert response.status_code == 201, response.text
    return response.json()

def test_full_vertical_slice(client):
    assert client.get('/api/health').json()['status'] == 'ok'
    settings = client.get('/api/settings')
    assert settings.status_code == 200, settings.text
    assert len(settings.json()['meals']) == 3
    item = activity(client)
    meeting = client.post('/api/events', json=dict(title='Стендап', on_date=DAY, start_time='10:00', end_time='11:00'))
    assert meeting.status_code == 201, meeting.text
    saved = client.post('/api/plans/generate', json={'on_date': DAY})
    assert saved.status_code == 200, saved.text
    blocks = saved.json()['blocks']
    assert any(b['title'] == 'Стендап' for b in blocks)
    assert any(b['title'] == 'Програмування' for b in blocks)
    assert len([b for b in blocks if b['kind'] == 'meal']) == 3
    for i, first in enumerate(blocks):
        for other in blocks[i+1:]:
            assert first['end_min'] <= other['start_min'] or other['end_min'] <= first['start_min']
    assert client.get('/api/plans/' + DAY).json()['id'] == saved.json()['id']
    aid = next(b['id'] for b in blocks if b['source_id'] == item['id'] and b['kind'] == 'activity')
    assert client.patch(f'/api/plans/blocks/{aid}', json={'status': 'done'}).status_code == 200
    rebuilt = client.post('/api/plans/generate', json={'on_date': DAY}).json()
    item_blocks = [b for b in rebuilt['blocks'] if b['source_id'] == item['id'] and b['kind'] == 'activity']
    assert len(item_blocks) == 1
    assert item_blocks[0]['status'] == 'done'

def test_impossible_day_reports_missing_work(client):
    settings = client.get('/api/settings').json()
    settings['wake_time'] = '08:00'
    settings['sleep_time'] = '12:00'
    settings['meals'] = []
    assert client.put('/api/settings', json=settings).status_code == 200
    activity(client, 'Завдання 1', duration_minutes=180, earliest_start='08:00', latest_end='12:00')
    activity(client, 'Завдання 2', duration_minutes=180, earliest_start='08:00', latest_end='12:00')
    plan = client.post('/api/plans/generate', json={'on_date': DAY}).json()
    assert plan['warnings'], plan
    assert sum(b['end_min']-b['start_min'] for b in plan['blocks'] if b['kind'] == 'activity') == 180

def test_fixed_calendar_conflict_warns(client):
    for title, start, end in [('A', '10:00', '11:00'), ('B', '10:30', '11:30')]:
        assert client.post('/api/events', json={'title':title, 'on_date':DAY, 'start_time':start, 'end_time':end}).status_code == 201
    plan = client.post('/api/plans/generate', json={'on_date': DAY}).json()
    assert any('Перетин календарних' in warning for warning in plan['warnings'])

def test_invalid_activity_and_event(client):
    assert client.post('/api/activities', json={'title':'x','duration_minutes':30,'earliest_start':'13:00','latest_end':'12:00'}).status_code == 422
    assert client.post('/api/activities', json={'title':'x','duration_minutes':30,'recurrence':'once'}).status_code == 422
    assert client.post('/api/events', json={'title':'x', 'on_date':DAY,'start_time':'12:00', 'end_time':'11:00'}).status_code == 422
    assert client.patch('/api/plans/blocks/9999', json={'status':'done'}).status_code == 404

def test_recurrence_and_optional(client):
    settings = client.get('/api/settings').json()
    settings['meals'] = []
    client.put('/api/settings', json=settings)
    activity(client, 'Будні', recurrence='weekdays', duration_minutes=30)
    activity(client, 'Вихідні', recurrence='weekends', duration_minutes=30)
    monday = client.post('/api/plans/generate', json={'on_date':'2026-10-12'}).json()
    sunday = client.post('/api/plans/generate', json={'on_date':'2026-10-11'}).json()
    assert 'Будні' in [b['title'] for b in monday['blocks']]
    assert 'Вихідні' not in [b['title'] for b in monday['blocks']]
    assert 'Вихідні' in [b['title'] for b in sunday['blocks']]

def test_edit_delete(client):
    item = activity(client)
    updated = {key:value for key,value in item.items() if key != 'id'}
    updated['title'] = 'Нова назва'
    assert client.put('/api/activities/' + str(item['id']), json=updated).json()['title'] == 'Нова назва'
    assert client.delete('/api/activities/' + str(item['id'])).status_code == 204
    assert client.get('/api/activities').json() == []

def test_meal_window_incompatibility_returns_warning(client):
    settings = client.get('/api/settings').json()
    settings['wake_time'] = '08:00'
    settings['sleep_time'] = '17:00'
    settings['meals'] = [{'key': 'lunch', 'title': 'Обід', 'earliest_start': '12:00', 'latest_end': '13:00', 'duration_minutes': 60}]
    assert client.put('/api/settings', json=settings).status_code == 200
    assert client.post('/api/events', json={'title':'Кол', 'on_date':DAY, 'start_time':'12:00', 'end_time':'13:00'}).status_code == 201
    result = client.post('/api/plans/generate', json={'on_date':DAY}).json()
    assert len(result['blocks']) == 1
    assert result['blocks'][0]['kind'] == 'event'
    assert any('Обід' in warning for warning in result['warnings'])
    assert any('60 хв' in warning for warning in result['warnings'])


def test_invalid_preferences_rejected(client):
    old = client.get('/api/settings').json()
    changed = dict(old, wake_time='23:00', sleep_time='08:00')
    assert client.put('/api/settings', json=changed).status_code == 422
    assert client.get('/api/settings').json() == old


def test_example_two_meetings_stays_feasible(client):
    activity(client, 'Англійська', duration_minutes=60, earliest_start='09:00', latest_end='20:00')
    activity(client, 'Програмування', duration_minutes=120, earliest_start='09:00', latest_end='19:00')
    activity(client, 'Прогулянка', duration_minutes=30, earliest_start='17:00', latest_end='23:00', required=False)
    for t, start, end in [('Нарада 1', '10:00', '11:00'), ('Нарада 2', '14:00', '15:00')]:
        assert client.post('/api/events',json={'title':t, 'on_date':DAY,'start_time':start,'end_time':end}).status_code == 201
    plan = client.post('/api/plans/generate', json={'on_date': DAY}).json()
    assert len(plan['blocks']) == 8
    assert not plan['warnings'], plan['warnings']
    assert len([x for x in plan['blocks'] if x['kind']=='meal']) == 3
    for i, first in enumerate(plan['blocks']):
        for second in plan['blocks'][i+1:]:
            assert first['end_min'] <= second['start_min'] or second['end_min'] <= first['start_min']
