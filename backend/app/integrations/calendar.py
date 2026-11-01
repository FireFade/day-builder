"""Read-only Google / Microsoft calendar import, with pagination and timezone conversion."""
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import httpx


async def pages(client, url, headers, params=None, *, provider):
    """Get all pages or fail atomically. Validate next links to prevent SSRF."""
    results = []
    for _ in range(30):
        response = await client.get(url, headers=headers, params=params, follow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        results.extend(payload.get("items" if provider == "google" else "value", []))
        if len(results) > 10000:
            raise ValueError("Занадто багато подій у календарі")
        if provider == "google":
            token = payload.get("nextPageToken")
            if not token:
                return results
            params = dict(params or {}, pageToken=token)
        else:
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                return results
            parsed = urlparse(next_link)
            if parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com" or not parsed.path.startswith("/v1.0/"):
                raise ValueError("Unsafe Microsoft Graph pagination link")
            url, params = next_link, None
    raise ValueError("Calendar pagination limit reached; shorten date range")


def to_aware(value, fallback_tz="UTC"):
    if isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=ZoneInfo(fallback_tz))
    if "dateTime" in value:
        return to_aware(value["dateTime"], value.get("timeZone") or fallback_tz)
    if "date" in value:
        return datetime.combine(date.fromisoformat(value["date"]), time.min, ZoneInfo(fallback_tz))
    raise ValueError("Missing event datetime")


def normalize(provider, calendar_id, event, local_tz: ZoneInfo, first: date, last: date):
    if event.get("status") == "cancelled" or event.get("isCancelled") or event.get("transparency") == "transparent" or event.get("showAs") in {"free", "workingElsewhere"}:
        return []
    ident = event.get("id")
    if not ident:
        return []
    fallback = local_tz.key if provider == "google" else "UTC"
    start = to_aware(event["start"], fallback).astimezone(local_tz)
    end = to_aware(event["end"], fallback).astimezone(local_tz)
    if end <= start:
        return []
    title = (event.get("summary") if provider == "google" else event.get("subject")) or "Зайнято"
    title = title[:160]
    results = []
    day = max(start.date(), first)
    while day <= min((end - timedelta(microseconds=1)).date(), last):
        day_start = datetime.combine(day, time.min, local_tz)
        day_end = day_start + timedelta(days=1)
        left, right = max(start, day_start), min(end, day_end)
        if left < right:
            # Existing Day Builder plan accepts HH:MM in one day only.
            a = left.hour * 60 + left.minute
            b = 1439 if right >= day_end else right.hour * 60 + right.minute
            if right.second or right.microsecond:
                b = min(1439, b + 1)
            if b > a:
                raw = f"{provider}|{calendar_id}|{ident}|{day.isoformat()}"
                results.append({
                    "title": title,
                    "on_date": day,
                    "start_time": f"{a//60:02d}:{a%60:02d}",
                    "end_time": f"{b//60:02d}:{b%60:02d}",
                    "source": provider,
                    "external_key": sha256(raw.encode()).hexdigest(),
                })
        day += timedelta(days=1)
    return results


async def get_remote_events(provider, access_token: str, start: date, end: date, tz_name: str):
    """Fetch all visible calendars and expand recurrence for inclusive local day window."""
    zone = ZoneInfo(tz_name)
    start_local = datetime.combine(start, time.min, zone)
    end_local = datetime.combine(end + timedelta(days=1), time.min, zone)
    low = start_local.isoformat()
    high = end_local.isoformat()
    headers = {"Authorization": "Bearer " + access_token}
    if provider == "microsoft":
        headers["Prefer"] = 'outlook.timezone="UTC"'
        base = "https://graph.microsoft.com/v1.0"
        cal_url = base + "/me/calendars"
    else:
        base = "https://www.googleapis.com/calendar/v3"
        cal_url = base + "/users/me/calendarList"
    async with httpx.AsyncClient(timeout=25) as client:
        calendars = await pages(client, cal_url, headers, provider=provider)
        if len(calendars) > 40:
            raise ValueError("Забагато календарів для одного підключення (ліміт 40)")
        result = []
        for cal in calendars:
            if cal.get("deleted") or cal.get("hidden") or cal.get("isDeleted"):
                continue
            cal_id = cal.get("id")
            if not cal_id:
                continue
            if provider == "google":
                url = base + "/calendars/" + quote(cal_id, safe="") + "/events"
                params = {"timeMin": low, "timeMax": high, "singleEvents": "true", "maxResults": 2500}
            else:
                url = base + "/me/calendars/" + quote(cal_id, safe="") + "/calendarView"
                params = {"startDateTime": low, "endDateTime": high, "$top": 1000}
            events = await pages(client, url, headers, params, provider=provider)
            for event in events:
                result.extend(normalize(provider, cal_id, event, zone, start, end))
    return list({e["external_key"]: e for e in result}.values())
