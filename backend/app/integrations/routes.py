"""Local-only OAuth integration routes. Not a multi-user SaaS security boundary."""
import json
import os
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CalendarConnection, CalendarEvent, DayPlan, OAuthAttempt
from . import oauth
from .sync_service import sync_calendar

def utc_timestamp(value):
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()

router = APIRouter(prefix="/api/integrations", tags=["calendar integrations"])


def validate_provider(provider):
    if provider not in oauth.PROVIDERS:
        raise HTTPException(404, "Calendar provider not supported")


def localhost_only(request: Request):
    if request.url.hostname not in {"localhost", "127.0.0.1", "testserver"}:
        raise HTTPException(403, "Localhost only")
    # A browser on another origin must not mutate the local API through cross-site requests.
    origin = request.headers.get("origin")
    if origin and origin not in {"http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173"}:
        raise HTTPException(403, "External origin rejected")


@router.get("")
def integrations(request: Request, db: Session = Depends(get_db)):
    localhost_only(request)
    rows = {item.provider: item for item in db.scalars(select(CalendarConnection))}
    return [{"provider": provider,
             "configured": oauth.configured(provider),
             "connected": provider in rows,
             "auto_sync_enabled": os.environ.get("DAYBUILDER_AUTO_SYNC", "0") == "1",
             "last_synced_at": utc_timestamp(rows[provider].last_synced_at) if provider in rows else None,
             "last_error": rows[provider].last_error if provider in rows else None}
            for provider in ("google", "microsoft")]


@router.get("/diagnostics")
def diagnostics(request: Request, db: Session = Depends(get_db)):
    """Safe local setup checklist; never returns secrets or access tokens."""
    localhost_only(request)
    connected = {c.provider: c for c in db.scalars(select(CalendarConnection))}
    payload = []
    for provider in ("google", "microsoft"):
        label = provider.upper()
        missing = [name for name in (f"{label}_CLIENT_ID", f"{label}_CLIENT_SECRET")
                   if not os.environ.get(name, "").strip()]
        payload.append({
            "provider": provider,
            "configured": not missing,
            "connected": provider in connected,
            "missing_variables": missing,
            "redirect_uri": oauth.redirect_uri(provider),
            "read_only": True,
            "needs_external_auth_test": provider not in connected,
            "status": ("connected" if provider in connected else
                       "ready_to_authorize" if not missing else "missing_configuration"),
            "notes": ("Після налаштування OAuth потрібно авторизуватися в браузері. "
                      "Робочий Microsoft 365 акаунт може вимагати дозволу адміністратора."),
        })
    return payload


@router.get("/{provider}/start")
def start(provider: str, request: Request, db: Session = Depends(get_db)):
    validate_provider(provider)
    localhost_only(request)
    if not oauth.configured(provider):
        raise HTTPException(503, f"Налаштуйте {provider.upper()}_CLIENT_ID та {provider.upper()}_CLIENT_SECRET у файлі .env")
    # A redirect on the same local machine ensures OAuth cookies and registered redirect host match.
    if request.url.hostname == "127.0.0.1":
        return RedirectResponse(f"http://localhost:8000/api/integrations/{provider}/start", status_code=302)
    state, verifier, challenge = oauth.new_attempt()
    # Prune old attempts; state is single-use and valid for 10 minutes.
    before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    db.execute(delete(OAuthAttempt).where(OAuthAttempt.created_at < before))
    db.add(OAuthAttempt(provider=provider, state_hash=oauth.sha256(state), verifier_ciphertext=oauth.seal(verifier)))
    db.commit()
    response = RedirectResponse(oauth.authorization_url(provider, state, challenge), status_code=302)
    response.set_cookie(f"db_oauth_{provider}", state, max_age=600, httponly=True, samesite="lax", secure=False, path=f"/api/integrations/{provider}/callback")
    return response


@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    validate_provider(provider)
    localhost_only(request)
    saved_cookie = request.cookies.get(f"db_oauth_{provider}")
    if not state or not saved_cookie or not __import__("hmac").compare_digest(state, saved_cookie):
        raise HTTPException(400, "OAuth state cookie mismatch")
    attempt = db.scalar(select(OAuthAttempt).where(OAuthAttempt.state_hash == oauth.sha256(state), OAuthAttempt.provider == provider))
    if not attempt:
        raise HTTPException(400, "OAuth state expired or already used")
    created = attempt.created_at.replace(tzinfo=timezone.utc) if attempt.created_at.tzinfo is None else attempt.created_at
    if datetime.now(timezone.utc) - created > timedelta(minutes=10):
        db.delete(attempt)
        db.commit()
        raise HTTPException(400, "OAuth attempt expired")
    verifier = oauth.unseal(attempt.verifier_ciphertext)
    db.delete(attempt)
    db.commit()
    response = RedirectResponse("/?calendar=connected" if code and not error else "/?calendar=denied", status_code=303)
    response.delete_cookie(f"db_oauth_{provider}", path=f"/api/integrations/{provider}/callback")
    if error or not code:
        return response
    try:
        token = oauth.normalized_tokens(await oauth.exchange(provider, code, verifier))
        stored = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == provider))
        if stored:
            old = json.loads(oauth.unseal(stored.token_ciphertext))
            if not token["refresh_token"]:
                token["refresh_token"] = old.get("refresh_token")
        else:
            stored = CalendarConnection(provider=provider, token_ciphertext="")
            db.add(stored)
        stored.token_ciphertext = oauth.seal(json.dumps(token))
        stored.status = "connected"
        stored.last_error = None
        db.commit()
    except (httpx.HTTPError, ValueError):
        response = RedirectResponse("/?calendar=oauth_failed", status_code=303)
        response.delete_cookie(f"db_oauth_{provider}", path=f"/api/integrations/{provider}/callback")
    return response


class SyncInput(BaseModel):
    on_date: date


@router.post("/{provider}/sync")
async def sync(provider: str, payload: SyncInput, request: Request, db: Session = Depends(get_db)):
    validate_provider(provider)
    localhost_only(request)
    stored = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == provider))
    if not stored:
        raise HTTPException(404, "Календар не підключено")
    try:
        return await sync_calendar(provider, payload.on_date, db)
    except ValueError as exc:
        raise HTTPException(502, "Не вдалося синхронізувати календар. Перевірте доступ і налаштування; за потреби підключіть заново.") from exc


@router.delete("/{provider}", status_code=204)
def disconnect(provider: str, request: Request, db: Session = Depends(get_db)):
    validate_provider(provider)
    localhost_only(request)
    connection = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == provider))
    if connection:
        db.delete(connection)
    dates = set(db.scalars(select(CalendarEvent.on_date).where(CalendarEvent.source == provider)))
    db.execute(delete(CalendarEvent).where(CalendarEvent.source == provider))
    if dates:
        for plan in db.scalars(select(DayPlan).where(DayPlan.on_date.in_(dates))):
            plan.calendar_stale = True
    db.commit()
    # Tokens are deleted locally; remote OAuth consent may also need revocation at provider.
