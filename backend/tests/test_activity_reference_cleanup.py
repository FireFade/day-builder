from datetime import date


def create_activity(client):
    response = client.post('/api/activities', json={
        'title': 'Linked activity', 'description': '', 'category': 'study',
        'duration_minutes': 60, 'priority': 3, 'required': True,
        'earliest_start': '08:00', 'latest_end': '17:00',
        'recurrence': 'daily', 'target_date': None, 'enabled': True,
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_deleting_activity_preserves_and_unlinks_inbox_and_habit(client):
    task = client.post('/api/inbox', json={'title': 'Keep this task'}).json()
    promoted = client.post(
        f"/api/inbox/{task['id']}/schedule",
        json={'on_date': '2026-10-12', 'category': 'study'},
    )
    assert promoted.status_code == 200, promoted.text
    promoted_task = promoted.json()
    activity_id = promoted_task['activity_id']
    habit = client.post('/api/habits', json={
        'title': 'Keep this habit', 'weekdays': list(range(7)),
        'minutes': 15, 'enabled': True, 'linked_activity_id': activity_id,
    })
    assert habit.status_code == 201, habit.text

    deleted = client.delete(f'/api/activities/{activity_id}')

    assert deleted.status_code == 204
    saved_task = next(x for x in client.get('/api/inbox').json() if x['id'] == task['id'])
    assert saved_task['activity_id'] is None
    assert saved_task['state'] == 'inbox'
    saved_habit = next(x for x in client.get('/api/habits?on_date=2026-10-12').json()
                       if x['id'] == habit.json()['id'])
    assert saved_habit['linked_activity_id'] is None

    rescheduled = client.post(
        f"/api/inbox/{task['id']}/schedule",
        json={'on_date': '2026-10-13', 'category': 'study'},
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()['activity_id'] is not None
    assert rescheduled.json()['state'] == 'done'


def test_deleting_activity_keeps_saved_plan_snapshot(client):
    activity_id = create_activity(client)
    on_date = date(2026, 10, 12).isoformat()
    preview = client.post('/api/plans/preview', json={'on_date': on_date})
    assert preview.status_code == 200, preview.text
    applied = client.post('/api/plans/apply', json={
        'on_date': on_date, 'revision': preview.json()['revision'],
    })
    assert applied.status_code == 200, applied.text
    before = next(x for x in applied.json()['blocks'] if x['source_id'] == activity_id)

    assert client.delete(f'/api/activities/{activity_id}').status_code == 204

    saved = client.get(f'/api/plans/{on_date}').json()
    historical = next(x for x in saved['blocks'] if x['id'] == before['id'])
    assert historical['title'] == 'Linked activity'
    assert saved['calendar_stale'] is True
