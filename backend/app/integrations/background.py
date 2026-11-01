"""Opt-in polling while the local FastAPI server is alive (not a cloud worker)."""
import asyncio
import os
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from ..db import SessionLocal
from ..models import CalendarConnection, Preferences
from .sync_service import sync_calendar

log = logging.getLogger(__name__)


def enabled():
    return os.environ.get("DAYBUILDER_AUTO_SYNC", "0") == "1"


def interval_seconds():
    try:
        return max(300, min(3600, int(os.environ.get("DAYBUILDER_SYNC_INTERVAL_SECONDS", "900"))))
    except ValueError:
        return 900


async def sync_once():
    # Do not hold a database session while sleeping; each provider is independent.
    with SessionLocal() as db:
        providers = list(db.scalars(select(CalendarConnection.provider)))
        setting = db.get(Preferences, 1)
        zone = setting.timezone if setting else "Europe/Kyiv"
    try:
        today = datetime.now(ZoneInfo(zone)).date()
    except ZoneInfoNotFoundError:
        today = datetime.now(ZoneInfo("UTC")).date()
    for provider in providers:
        with SessionLocal() as db:
            try:
                await sync_calendar(provider, today, db)
            except (ValueError, LookupError):
                # Expected provider/OAuth errors are stored as a safe code.
                continue
            except Exception:
                # Background worker should not permanently stop on one bad provider.
                # Never log exception details: some libraries include OAuth URLs/tokens.
                log.error("Unexpected calendar sync error for provider=%s", provider)


async def worker():
    # First import soon after the server starts; subsequent imports run periodically.
    await asyncio.sleep(8)
    while True:
        await sync_once()
        await asyncio.sleep(interval_seconds())


@asynccontextmanager
async def lifecycle(app):
    task = asyncio.create_task(worker()) if enabled() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
