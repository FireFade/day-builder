"""v0.3 regression coverage: change detection, stale marking, no-op and background behavior."""
import json
from datetime import date

import pytest
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.integrations import oauth, sync_service, background
from app.models import CalendarConnection, CalendarEvent, DayPlan


def add_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(oauth, 'VAULT_KEY_FILE', tmp_path / 'sync.key')
    dep = app.dependency_overrides[get_db]
    g = dep()
    session = next(g)
    session.add(CalendarConnection(provider='google', token_ciphertext=oauth.seal(json.dumps({
        'access_token': 'TEST-ACCESS', 'refresh_token': 'TEST-REFRESH', 'expires_at': 9999999999
    }))))
    session.commit()
    g.close()


def meeting(start='10:00', title='Work meeting'):
    return [dict(title=title, on_date=date(2026,10,11), start_time=start, end_time='11:00',
                 source='google', external_key='stable-provider-key')]


def test_change_marks_saved_plan_stale_and_regenerate_clears(client, monkeypatch, tmp_path):
    add_connection(tmp_path, monkeypatch)
    items = meeting()
    async def calendar(*args):
        return [dict(x) for x in items]
    monkeypatch.setattr(sync_service, 'get_remote_events', calendar)
    first = client.post('/api/integrations/google/sync', json={'on_date': '2026-10-11'})
    assert first.status_code == 200 and first.json()['change_count'] == 1
    assert first.json()['changed_dates'] == ['2026-10-11']

    made = client.post('/api/plans/generate', json={'on_date':'2026-10-11'})
    assert made.status_code == 200, made.text
    assert made.json()['calendar_stale'] is False
    event_id = client.get('/api/events?on_date=2026-10-11').json()[0]['id']

    identical = client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'})
    assert identical.status_code == 200 and identical.json()['change_count'] == 0
    assert client.get('/api/events?on_date=2026-10-11').json()[0]['id'] == event_id
    assert client.get('/api/plans/2026-10-11').json()['calendar_stale'] is False

    items[:] = meeting(start='09:30')
    changed = client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'})
    assert changed.status_code == 200 and changed.json()['change_count'] == 1
    assert client.get('/api/plans/2026-10-11').json()['calendar_stale'] is True
    assert client.get('/api/plans/2026-10-12').json() is None
    rebuilt = client.post('/api/plans/generate', json={'on_date':'2026-10-11'}).json()
    assert rebuilt['calendar_stale'] is False
    assert client.get('/api/events?on_date=2026-10-11').json()[0]['start_time'] == '09:30'


def test_removed_event_and_disconnect_mark_plan_stale(client, monkeypatch, tmp_path):
    add_connection(tmp_path, monkeypatch)
    items = meeting()
    async def remote(*args):
        return list(items)
    monkeypatch.setattr(sync_service, 'get_remote_events', remote)
    assert client.post('/api/integrations/google/sync',json={'on_date':'2026-10-11'}).status_code == 200
    assert client.post('/api/plans/generate',json={'on_date':'2026-10-11'}).status_code == 200
    items.clear()
    assert client.post('/api/integrations/google/sync',json={'on_date':'2026-10-11'}).json()['change_count'] == 1
    assert client.get('/api/plans/2026-10-11').json()['calendar_stale']
    items.extend(meeting())
    assert client.post('/api/integrations/google/sync',json={'on_date':'2026-10-11'}).status_code == 200
    assert client.post('/api/plans/generate',json={'on_date':'2026-10-11'}).json()['calendar_stale'] is False
    assert client.delete('/api/integrations/google').status_code == 204
    assert client.get('/api/plans/2026-10-11').json()['calendar_stale'] is True


def test_bad_import_keeps_previous_events(client, monkeypatch, tmp_path):
    add_connection(tmp_path, monkeypatch)
    async def fine(*args):
        return meeting()
    monkeypatch.setattr(sync_service, 'get_remote_events', fine)
    assert client.post('/api/integrations/google/sync',json={'on_date':'2026-10-11'}).status_code == 200
    async def corrupted(*args):
        return meeting(start='09:00') + meeting(start='08:00')  # duplicate provider IDs
    monkeypatch.setattr(sync_service, 'get_remote_events', corrupted)
    response=client.post('/api/integrations/google/sync',json={'on_date':'2026-10-11'})
    assert response.status_code == 502
    assert 'TEST-ACCESS' not in response.text
    assert client.get('/api/events?on_date=2026-10-11').json()[0]['start_time']=='10:00'
    assert client.get('/api/integrations').json()[0]['last_error']=='sync_failed'


def test_background_disabled_and_interval_bounds(monkeypatch):
    monkeypatch.delenv('DAYBUILDER_AUTO_SYNC', raising=False)
    assert background.enabled() is False
    monkeypatch.setenv('DAYBUILDER_AUTO_SYNC', '1')
    assert background.enabled() is True
    for setting, expected in [('0', 300), ('30',300), ('900',900), ('999999',3600), ('oops',900)]:
        monkeypatch.setenv('DAYBUILDER_SYNC_INTERVAL_SECONDS', setting)
        assert background.interval_seconds() == expected
