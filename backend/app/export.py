"""Read-only download of an entire locally scheduled day as standard iCalendar."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from fastapi.responses import Response
from .manual_plan import get_plan
from .models import Preferences


def _escape(value: str) -> str:
    return str(value).replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(',', '\\,').replace(';','\\;')

def _utc(day, mins: int, tz: ZoneInfo) -> str:
    dt = datetime.combine(day, time(hour=(mins//60)%24, minute=mins%60), tzinfo=tz)
    if mins == 1440:
        from datetime import timedelta
        dt = dt + timedelta(days=1)
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def export_calendar(get_db, on_date):
    plan = get_plan(get_db, on_date)
    prefs = get_db.get(Preferences, 1)
    tz = ZoneInfo(prefs.timezone if prefs else 'Europe/Kyiv')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Day Builder//Personal Planner//UK', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for b in plan.blocks:
        if b.status == 'skipped':
            continue
        lines += ['BEGIN:VEVENT', f'UID:daybuilder-{plan.id}-{b.id}@local', f'DTSTAMP:{stamp}',
                  f'DTSTART:{_utc(on_date,b.start_min,tz)}', f'DTEND:{_utc(on_date,b.end_min,tz)}',
                  f'SUMMARY:{_escape(b.title)}', f'DESCRIPTION:{_escape(b.explanation)}',
                  f'CATEGORIES:{_escape(b.category)}', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    content = '\r\n'.join(lines) + '\r\n'
    return Response(content=content, media_type='text/calendar; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="daybuilder-{on_date}.ics"',
                             'Cache-Control':'no-store'})
