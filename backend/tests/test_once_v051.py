"""BUG-001: a one-time activity must not leak into other days."""

from datetime import date


def _activity(client, recurrence="once", target_date="2026-10-12", title="Лише 12 жовтня"):
    data = {
        "title": title,
        "duration_minutes": 60,
        "earliest_start": "09:00",
        "latest_end": "17:00",
        "recurrence": recurrence,
        "target_date": target_date,
    }
    response = client.post('/api/activities', json=data)
    assert response.status_code == 201, response.text
    return response.json()


def _activities_in_plan(plan):
    return [block for block in plan['blocks'] if block['kind'] == 'activity']


def _apply_preview(client, day):
    proposal = client.post('/api/plans/preview', json={'on_date': day})
    assert proposal.status_code == 200, proposal.text
    reply = client.post('/api/plans/apply', json={'on_date': day, 'revision': proposal.json()['revision']})
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_one_time_only_target_date_preview_and_confirm(client):
    a = _activity(client)
    assert a['recurrence'] == 'once'
    assert a['target_date'] == '2026-10-12'
    for day, expected in [('2026-10-11', 0), ('2026-10-12', 1), ('2026-10-13', 0)]:
        preview = client.post('/api/plans/preview', json={'on_date': day}).json()
        assert len([b for b in preview['blocks'] if b['source_id'] == a['id'] and b['kind'] == 'activity']) == expected
        plan = _apply_preview(client, day)
        assert len([b for b in _activities_in_plan(plan) if b['source_id'] == a['id']]) == expected
        assert len([b for b in _activities_in_plan(client.get('/api/plans/' + day).json()) if b['source_id'] == a['id']]) == expected


def test_fix_existing_daily_activity_keeps_wrong_date_stale_until_user_accepts(client):
    a = _activity(client, recurrence='daily', target_date=None, title='Не мала повторюватися')
    wrong = _apply_preview(client, '2026-10-13')
    wrong_block = next(b for b in wrong['blocks'] if b['kind'] == 'activity' and b['source_id'] == a['id'])
    assert client.patch(f"/api/plans/blocks/{wrong_block['id']}", json={'status':'done'}).status_code == 200
    right = _apply_preview(client, '2026-10-12')

    # The real user fixes a mistakenly daily activity to one-time.
    edited = {key: value for key, value in a.items() if key != 'id'}
    edited.update(recurrence='once', target_date='2026-10-12')
    update = client.put(f"/api/activities/{a['id']}", json=edited)
    assert update.status_code == 200, update.text
    assert client.get('/api/plans/2026-10-13').json()['calendar_stale'] is True
    assert client.get('/api/plans/2026-10-12').json()['calendar_stale'] is True
    assert client.get('/api/plans/2026-10-13').json()['blocks']  # no silent deletion before confirmation

    new_preview = client.post('/api/plans/preview', json={'on_date': '2026-10-13'}).json()
    assert all(b['source_id'] != a['id'] for b in _activities_in_plan(new_preview))
    rebuilt = _apply_preview(client, '2026-10-13')
    assert not [b for b in _activities_in_plan(rebuilt) if b['source_id'] == a['id']]
    assert rebuilt['calendar_stale'] is False
    # Active on 12 Oct; old pending content still correct after replan.
    still_right = _apply_preview(client, '2026-10-12')
    assert [b for b in _activities_in_plan(still_right) if b['source_id'] == a['id']]


def test_legacy_generate_does_not_preserve_wrong_date_locked_block(client):
    a = _activity(client, recurrence='daily', target_date=None)
    old = client.post('/api/plans/generate', json={'on_date': '2026-10-11'}).json()
    block = next(b for b in _activities_in_plan(old) if b['source_id'] == a['id'])
    updated = client.patch(f"/api/plans/blocks/{block['id']}", json={'status': 'done'})
    assert updated.status_code == 200
    update = {key: value for key, value in a.items() if key != 'id'}
    update.update(recurrence='once', target_date='2026-10-12')
    assert client.put(f"/api/activities/{a['id']}", json=update).status_code == 200
    fixed = client.post('/api/plans/generate', json={'on_date': '2026-10-11'}).json()
    assert all(b['source_id'] != a['id'] for b in _activities_in_plan(fixed))


def test_creating_deleting_activity_marks_existing_plan_stale(client):
    _apply_preview(client, '2026-10-12')
    created = _activity(client)
    assert client.get('/api/plans/2026-10-12').json()['calendar_stale'] is True
    _apply_preview(client, '2026-10-12')
    assert client.get('/api/plans/2026-10-12').json()['calendar_stale'] is False
    assert client.delete(f"/api/activities/{created['id']}").status_code == 204
    assert client.get('/api/plans/2026-10-12').json()['calendar_stale'] is True


def test_one_time_requires_a_date(client):
    invalid = client.post('/api/activities', json={'title': 'Разове', 'duration_minutes': 60, 'recurrence': 'once'})
    assert invalid.status_code == 422


def test_repeating_activity_rejects_ignored_target_date(client):
    response = client.post('/api/activities', json={
        'title': 'Неправильно задана дата', 'duration_minutes': 60,
        'recurrence': 'daily', 'target_date': '2026-10-12',
    })
    assert response.status_code == 422
    assert 'Дата застосовується тільки' in response.text
