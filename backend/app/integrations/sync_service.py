"""Shared manual/background calendar synchronization with transactional change tracking."""
import json
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfoNotFoundError
from cryptography.fernet import InvalidToken

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import CalendarConnection, CalendarEvent, DayPlan, Preferences
from . import oauth
from .calendar import get_remote_events


def import_window(day: date):
    return day - timedelta(days=2), day + timedelta(days=14)


def event_signature(event):
    return (event.title, event.start_time, event.end_time)


async def sync_calendar(provider: str, day: date, db: Session) -> dict:
    """Fetch first, then atomically change imported events and mark affected plans stale.

    Raises for network/auth errors; no existing events are removed on fetch failures.
    """
    connection = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == provider))
    if not connection:
        raise LookupError("Calendar not connected")
    pref = db.get(Preferences, 1)
    zone = pref.timezone if pref else "Europe/Kyiv"
    begin, end = import_window(day)
    try:
        token = json.loads(oauth.unseal(connection.token_ciphertext))
        if token.get("expires_at", 0) < time.time():
            if not token.get("refresh_token"):
                raise ValueError("OAuth reconnect required")
            token = oauth.normalized_tokens(await oauth.refresh(provider, token["refresh_token"]), token)
            # Save rotated refresh credentials independently from import success.
            connection.token_ciphertext = oauth.seal(json.dumps(token))
            db.commit()
        incoming = await get_remote_events(provider, token["access_token"], begin, end, zone)
        if len(incoming) > 10000:
            raise ValueError("Import limit exceeded")
        if any(item["source"] != provider or not begin <= item["on_date"] <= end for item in incoming):
            raise ValueError("Invalid provider event")
        # Validate uniqueness before touching imported rows.
        if len({item["external_key"] for item in incoming}) != len(incoming):
            raise ValueError("Duplicate external event key")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ZoneInfoNotFoundError, InvalidToken) as exc:
        db.rollback()
        connection = db.scalar(select(CalendarConnection).where(CalendarConnection.provider == provider))
        if connection:
            connection.last_error = "sync_failed"
            db.commit()
        raise ValueError("Calendar synchronization failed") from exc

    existing = db.scalars(select(CalendarEvent).where(CalendarEvent.source == provider,
                                                      CalendarEvent.on_date >= begin,
                                                      CalendarEvent.on_date <= end)).all()
    previous_by_key = {entry.external_key: entry for entry in existing}
    incoming_by_key = {item["external_key"]: item for item in incoming}
    changed_dates = set()
    for key in set(previous_by_key) | set(incoming_by_key):
        before, after = previous_by_key.get(key), incoming_by_key.get(key)
        if before is None:
            changed_dates.add(after["on_date"])
        elif after is None:
            changed_dates.add(before.on_date)
        elif event_signature(before) != (after["title"], after["start_time"], after["end_time"]):
            changed_dates.add(before.on_date)
            changed_dates.add(after["on_date"])

    if changed_dates:
        # Replace only after a COMPLETE successful fetch; duplicates cannot accumulate.
        db.execute(delete(CalendarEvent).where(CalendarEvent.source == provider,
                                               CalendarEvent.on_date >= begin,
                                               CalendarEvent.on_date <= end))
        db.add_all([CalendarEvent(**item) for item in incoming])
        plans = db.scalars(select(DayPlan).where(DayPlan.on_date.in_(changed_dates))).all()
        for plan in plans:
            plan.calendar_stale = True
    connection.last_synced_at = datetime.now(timezone.utc)
    connection.last_error = None
    db.commit()
    return {"provider": provider, "events_imported": len(incoming),
            "changed_dates": sorted(changed_dates), "change_count": len(changed_dates),
            "start": begin, "end": end,
            "note": "За появи змін перебудуйте відповідні плани дня"}
