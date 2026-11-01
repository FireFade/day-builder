"""Integration tests use fake OAuth/network responses, never live credentials."""
import json
import asyncio
from datetime import date
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.integrations import oauth
from app.integrations.calendar import normalize, pages
from app.models import CalendarConnection, CalendarEvent


def db_session():
    dep = app.dependency_overrides[get_db]
    generator = dep()
    session = next(generator)
    return session, generator


def test_not_configured_and_localhost_only(client, monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
    response = client.get('/api/integrations')
    assert response.status_code == 200
    assert response.json()[0]['configured'] is False
    assert client.get('/api/integrations/google/start').status_code == 503
    assert client.get('/api/integrations', headers={'Origin':'https://attacker.example'}).status_code == 403
    assert client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'}).status_code == 404


def test_auth_code_exchange_state_and_encryption(client, monkeypatch, tmp_path):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'sample-client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'sample-client-secret')
    monkeypatch.setattr(oauth, 'VAULT_KEY_FILE', tmp_path / 'vault.key')
    async def fake_exchange(provider, code, verifier):
        assert provider == 'google' and code == 'code-sample'
        assert verifier and len(verifier) > 30
        return {'access_token':'TOP-SECRET-ACCESS', 'refresh_token':'TOP-SECRET-REFRESH', 'expires_in':3600}
    monkeypatch.setattr(oauth, 'exchange', fake_exchange)
    start = client.get('/api/integrations/google/start', follow_redirects=False)
    assert start.status_code == 302
    parsed = urlparse(start.headers['location'])
    assert parsed.hostname == 'accounts.google.com'
    query = parse_qs(parsed.query)
    assert query['access_type'] == ['offline']
    assert query['code_challenge_method'] == ['S256']
    assert 'calendar.readonly' in query['scope'][0]
    assert 'access_token' not in start.headers['location']
    state = query['state'][0]
    assert client.get('/api/integrations/google/callback', params={'state':'WRONG','code':'code-sample'}, follow_redirects=False).status_code == 400
    completed = client.get('/api/integrations/google/callback', params={'state':state,'code':'code-sample'}, follow_redirects=False)
    assert completed.status_code == 303
    assert completed.headers['location'] == '/?calendar=connected'
    assert client.get('/api/integrations/google/callback', params={'state':state,'code':'code-sample'}, follow_redirects=False).status_code == 400
    db, generator = db_session()
    stored = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == 'google'))
    assert stored is not None
    assert 'TOP-SECRET-' not in stored.token_ciphertext
    assert json.loads(oauth.unseal(stored.token_ciphertext))['refresh_token'] == 'TOP-SECRET-REFRESH'
    generator.close()
    assert client.get('/api/integrations').json()[0]['connected'] is True


def test_sync_atomic_idempotent_refresh_and_disconnect(client, monkeypatch, tmp_path):
    monkeypatch.setattr(oauth, 'VAULT_KEY_FILE', tmp_path / 'vault.key')
    session, generator = db_session()
    session.add(CalendarConnection(provider='google', token_ciphertext=oauth.seal(json.dumps({'access_token':'OLD', 'refresh_token':'R1','expires_at':0}))))
    session.commit()
    generator.close()
    async def fake_refresh(provider, refresh_token):
        assert provider=='google' and refresh_token=='R1'
        return {'access_token':'FRESH','expires_in':3600}
    async def fake_events(provider, access_token, begin, end, tz):
        assert provider=='google' and access_token=='FRESH' and tz == 'Europe/Kyiv'
        return [{'title':'Google work', 'on_date':date(2026,10,11), 'start_time':'10:00', 'end_time':'11:00', 'source':'google','external_key':'stable-key'}]
    monkeypatch.setattr(oauth, 'refresh', fake_refresh)
    from app.integrations import sync_service
    monkeypatch.setattr(sync_service, 'get_remote_events', fake_events)
    manual = client.post('/api/events',json={'title':'Local', 'on_date':'2026-10-11', 'start_time':'14:00','end_time':'15:00'})
    assert manual.status_code == 201
    resp = client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'})
    assert resp.status_code == 200,resp.text
    assert resp.json()['events_imported']==1
    assert len(client.get('/api/events?on_date=2026-10-11').json())==2
    assert client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'}).status_code==200
    events = client.get('/api/events?on_date=2026-10-11').json()
    assert len(events)==2
    external = next(e for e in events if e['source']=='google')
    assert client.delete('/api/events/'+str(external['id'])).status_code==409
    async def failing_events(*args,**kwargs):
        raise httpx.ConnectError('secrets should not leak')
    monkeypatch.setattr(sync_service, 'get_remote_events', failing_events)
    assert client.post('/api/integrations/google/sync', json={'on_date':'2026-10-11'}).status_code==502
    assert len(client.get('/api/events?on_date=2026-10-11').json())==2
    assert client.delete('/api/integrations/google').status_code == 204
    assert client.get('/api/integrations').json()[0]['connected'] is False
    assert client.get('/api/events?on_date=2026-10-11').json()[0]['source']=='manual'


def test_normalization_microsoft_google_dst_overnight():
    tz=ZoneInfo('Europe/Kyiv')
    event={'id':'part-1','subject':' Teams call ','start':{'dateTime':'2026-10-24T20:30:00','timeZone':'UTC'},'end':{'dateTime':'2026-10-25T01:30:00','timeZone':'UTC'}, 'showAs':'busy'}
    output=normalize('microsoft','work',event,tz,date(2026,10,24),date(2026,10,25))
    assert len(output)==2
    assert output[0]['on_date']==date(2026,10,25) or output[0]['on_date']==date(2026,10,24)
    assert len({x['external_key'] for x in output})==2
    assert all(x['start_time']<x['end_time'] for x in output)
    assert normalize('microsoft','c',dict(event,showAs='free'),tz,date(2026,10,24),date(2026,10,25))==[]
    google={'id':'a','summary':'All day','start':{'date':'2026-10-25'},'end':{'date':'2026-10-26'}}
    assert normalize('google','personal',google,tz,date(2026,10,25),date(2026,10,25))[0]['end_time']=='23:59'
    assert normalize('google','personal',dict(google,status='cancelled'),tz,date(2026,10,25),date(2026,10,25))==[]


def test_graph_pagination_does_not_allow_arbitrary_hosts():
    class ResponseClient:
        async def get(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request('GET',url), json={'value':[{'id':'first'}], '@odata.nextLink':'http://evil.local/steal'})
    with pytest.raises(ValueError,match='Unsafe'):
        asyncio.run(pages(ResponseClient(), 'https://graph.microsoft.com/v1.0/me/calendars',{},provider='microsoft'))
