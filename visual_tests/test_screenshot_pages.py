from __future__ import annotations

import json
import os
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
TEST_ROOT = PROJECT_ROOT / "visual_tests"
BASELINES = TEST_ROOT / "snapshots" / "approved"
RESULTS = TEST_ROOT / "results"
FIXED_DATE = "2026-11-02"
VIEWPORT = {"width": 1440, "height": 1000}

PAGE_CASES = [
    ("dashboard", "Твій день — у твоїх руках ✨", "План на сьогодні", "dashboard"),
    ("day", "Мій день", "Розклад дня", "day"),
    ("activities", "Мої активності", "Ранкова зарядка", "activities"),
    ("calendar", "Календар подій", "Підключені календарі", "calendar"),
    ("settings", "Мій ритм дня", "Сон і пробудження", "settings"),
]

ACTIVITIES = [
    {
        "id": 1,
        "title": "Ранкова зарядка",
        "description": "Коротке тренування перед початком дня.",
        "category": "health",
        "duration_minutes": 30,
        "priority": 4,
        "required": True,
        "enabled": True,
        "earliest_start": "08:00",
        "latest_end": "10:00",
        "recurrence": "weekdays",
        "target_date": None,
    },
    {
        "id": 2,
        "title": "Підготовка до лабораторної",
        "description": "Перевірити код і зібрати матеріали.",
        "category": "study",
        "duration_minutes": 90,
        "priority": 5,
        "required": True,
        "enabled": True,
        "earliest_start": "09:00",
        "latest_end": "13:00",
        "recurrence": "weekdays",
        "target_date": None,
    },
    {
        "id": 3,
        "title": "Прогулянка",
        "description": "Час на відпочинок і свіже повітря.",
        "category": "leisure",
        "duration_minutes": 45,
        "priority": 2,
        "required": False,
        "enabled": True,
        "earliest_start": "16:00",
        "latest_end": "20:00",
        "recurrence": "daily",
        "target_date": None,
    },
]

EVENTS = [
    {
        "id": 10,
        "title": "Командне планування",
        "on_date": FIXED_DATE,
        "start_time": "11:00",
        "end_time": "11:45",
        "source": "manual",
    },
    {
        "id": 11,
        "title": "Консультація з викладачем",
        "on_date": FIXED_DATE,
        "start_time": "14:00",
        "end_time": "14:30",
        "source": "google",
    },
]

PREFERENCES = {
    "wake_time": "07:30",
    "sleep_time": "23:00",
    "timezone": "Europe/Kyiv",
    "energy_peak_start": "09:00",
    "energy_peak_end": "12:00",
    "meals": [
        {"key": "breakfast", "title": "Сніданок", "earliest_start": "08:00", "latest_end": "09:00", "duration_minutes": 30},
        {"key": "lunch", "title": "Обід", "earliest_start": "12:00", "latest_end": "14:00", "duration_minutes": 45},
        {"key": "dinner", "title": "Вечеря", "earliest_start": "18:00", "latest_end": "20:00", "duration_minutes": 45},
    ],
}

PLAN = {
    "id": 1,
    "on_date": FIXED_DATE,
    "warnings": [],
    "calendar_stale": False,
    "blocks": [
        {
            "id": 21,
            "kind": "activity",
            "source_id": 2,
            "title": "Підготовка до лабораторної",
            "category": "study",
            "start_min": 555,
            "end_min": 645,
            "status": "pending",
            "explanation": "Найпродуктивніший час для зосередженої роботи.",
            "is_locked": False,
        },
        {
            "id": 22,
            "kind": "event",
            "source_id": 10,
            "title": "Командне планування",
            "category": "work",
            "start_min": 660,
            "end_min": 705,
            "status": "pending",
            "explanation": "Подія календаря зафіксована.",
            "is_locked": True,
        },
        {
            "id": 23,
            "kind": "activity",
            "source_id": 1,
            "title": "Ранкова зарядка",
            "category": "health",
            "start_min": 735,
            "end_min": 765,
            "status": "done",
            "explanation": "Заряд енергії на день.",
            "is_locked": False,
        },
    ],
}

DEFECT_CSS = """
html { filter: grayscale(1) contrast(1.35) !important; }
.sidebar { width: 340px !important; flex-basis: 340px !important; background: #d7193f !important; }
.heading h1 { color: #b00020 !important; font-size: 42px !important; }
.panel, .hero, .activity-card { border-radius: 0 !important; box-shadow: none !important; }
"""


class WebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        path = urlsplit(path).path
        if path in ("/", "/index.html"):
            return str(WEB_ROOT / "index.html")
        if path.startswith("/assets/"):
            return str(WEB_ROOT / path.removeprefix("/assets/"))
        return str(WEB_ROOT / "__not_found__")

    def log_message(self, *_args):
        return


@pytest.fixture(scope="session")
def web_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def api_payload(path: str):
    if path == "/api/activities":
        return ACTIVITIES
    if path == "/api/events" or path.startswith("/api/events/range"):
        return EVENTS
    if path == "/api/settings":
        return PREFERENCES
    if path.startswith("/api/plans/") and path.endswith("/history"):
        return {"undo_available": False, "redo_available": False, "entries": []}
    if path.startswith("/api/plans/"):
        return PLAN
    if path == "/api/integrations/diagnostics":
        return [
            {"provider": "google", "connected": False, "configured": False, "redirect_uri": "http://127.0.0.1:8000/api/integrations/google/callback", "missing_variables": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]},
            {"provider": "microsoft", "connected": False, "configured": False, "redirect_uri": "http://127.0.0.1:8000/api/integrations/microsoft/callback", "missing_variables": ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"]},
        ]
    if path == "/api/reflections/" + FIXED_DATE:
        return None
    if path.startswith("/api/"):
        return []
    return None


@pytest.fixture(scope="session")
def browser():
    browser_executable = os.environ.get(
        "DAY_BUILDER_BROWSER", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    )
    with sync_playwright() as playwright:
        if Path(browser_executable).is_file():
            instance = playwright.chromium.launch(headless=True, executable_path=browser_executable)
        else:
            instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, web_url):
    context = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=1,
        locale="uk-UA",
        timezone_id="Europe/Kyiv",
        color_scheme="light",
    )
    page = context.new_page()
    page.emulate_media(reduced_motion="reduce")
    page.add_init_script(
        """(() => {
          const NativeDate = Date;
          const fixed = NativeDate.parse('2026-11-02T07:00:00Z');
          class StableDate extends NativeDate {
            constructor(...args) { super(...(args.length ? args : [fixed])); }
            static now() { return fixed; }
          }
          Object.defineProperty(globalThis, 'Date', { value: StableDate });
          localStorage.clear();
        })();"""
    )

    def mock_api(route):
        payload = api_payload(urlsplit(route.request.url).path)
        route.fulfill(
            status=200,
            content_type="application/json; charset=utf-8",
            body=json.dumps(payload, ensure_ascii=False),
        )

    page.route("**/api/**", mock_api)
    page.goto(web_url, wait_until="networkidle")
    page.locator(".shell").wait_for()
    page.locator("h1").wait_for()
    page.evaluate("document.fonts.ready")
    yield page
    context.close()


def screenshot_diff_ratio(expected_path: Path, actual_path: Path) -> float:
    with Image.open(expected_path).convert("RGB") as expected, Image.open(actual_path).convert("RGB") as actual:
        width = max(expected.width, actual.width)
        height = max(expected.height, actual.height)
        expected_canvas = Image.new("RGB", (width, height), "white")
        actual_canvas = Image.new("RGB", (width, height), "white")
        expected_canvas.paste(expected, (0, 0))
        actual_canvas.paste(actual, (0, 0))
        difference = ImageChops.difference(expected_canvas, actual_canvas).convert("L")
        histogram = difference.histogram()
        changed_pixels = sum(histogram[17:])
        return changed_pixels / (width * height)


@pytest.mark.parametrize("page_id,title,ready_text,file_stem", PAGE_CASES, ids=[case[0] for case in PAGE_CASES])
def test_day_builder_page_matches_approved_screenshot(page: Page, page_id: str, title: str, ready_text: str, file_stem: str):
    if page_id != "dashboard":
        page.locator(f'.nav-item[data-page="{page_id}"]').click()
    page.locator("h1").wait_for()
    assert page.locator("h1").inner_text().strip() == title
    page.get_by_text(ready_text, exact=False).first.wait_for()

    defects = os.environ.get("DAY_BUILDER_VISUAL_DEFECTS") == "1"
    if defects:
        page.add_style_tag(content=DEFECT_CSS)
    output_dir = RESULTS / ("defects" if defects else "current")
    output_dir.mkdir(parents=True, exist_ok=True)
    actual_path = output_dir / f"{file_stem}.png"
    page.screenshot(path=str(actual_path), full_page=True, animations="disabled")

    baseline_path = BASELINES / f"{file_stem}.png"
    if os.environ.get("DAY_BUILDER_UPDATE_BASELINES") == "1":
        BASELINES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(actual_path, baseline_path)
        return

    assert baseline_path.is_file(), f"Approved baseline is missing: {baseline_path}"
    diff_ratio = screenshot_diff_ratio(baseline_path, actual_path)
    assert diff_ratio <= 0.001, (
        f"Visual mismatch on page '{page_id}': {diff_ratio:.2%} of pixels differ. "
        f"Current screenshot: {actual_path}; approved baseline: {baseline_path}"
    )
