# Day Builder v1.0 beta

## Аудит і стабілізаційні виправлення (2026-11-02)
- Додано `docs/TECHNICAL-AUDIT-v1.0.md` з інвентаризацією функцій, ризиками та планом стабілізації.
- Видалення активності тепер від'єднує, але зберігає Inbox-задачі й звички; Inbox-задача повертається у стан «вхідні» та може бути запланована повторно.
- Додано два регресійні тести для збереження зв'язків і вже створеного плану.
- Live Google OAuth і ручні браузерні UAT-сценарії залишаються неперевіреними.

- Smart Planning activity policies (recurrence, buffers, preferred hours, energy peaks, dependency DAG, goal link, due date)
- Inbox with subtasks, Goals, Habits, templates and week goals progress
- Move pending activities to tomorrow, reminder snooze/dismiss
- Calendar month/week grid, light/dark themes, responsive navigation
- Offline read-only shell cache and user-facing SQLite backup without secrets
- Alembic 0006, new backend and developer tests

---

## v0.6.0 (2026-10-12) — Weekly planning, focus and insights
- Weekly preview (seven days), checked multi-day explicit approval with SHA-256 revision verification and atomic transaction.
- Analytics for 7/30/90 days based on persisted records only.
- Focus Pomodoro-style timer (5–90 min), pause/resume, completed-minute logging, session deletion.
- Day reflections with mood, energy, and note saved per day.
- Configurable in-tab browser reminder lead time.
- Responsive checkbox/modal regression fix retained from v0.5.x; once-only recurrence fix retained.
- Migration `0005_insights_focus.py`; old SQLite preferences, plans, and Google connection remain intact.
- 53 passing backend tests, static Chromium UI checks (1440/1100/390 px), and SQLite migration check.
- React prototype still lacks feature parity; live provider OAuth + Windows E2E not yet reverified for v0.6.

## v0.5.1 — Fix one-time activity recurrence (BUG-001)
- Show the one-time date only when recurrence is `once`; explain scheduling behaviour, show recurrence on activity cards.
- Invalidate previously saved plans after editing activity definitions.
- Do not preserve completed/locked activity blocks if their source activity no longer applies to that day.
- Added regression tests for calendar-date boundaries, stale plans, completed activity preservation, and invalid recurrence/date combinations.

# Зміни Day Builder

## v0.5 — Manual day builder
- Ручна зміна часу, назви, категорії, тривалості й закріплення блоків без модифікації Google Calendar.
- Перетягування справ (drag-and-drop), мобільні стрілки для перестановки, перевірка обмежень на backend.
- Власні часові блоки (створення/видалення/редагування), збереження їх при переплануванні.
- Постійна історія Undo/Redo до 30 ручних змін, очищення після перебудови дня.
- Позначення справ як виконаних і пропущених.
- Експорт `.ics`, браузерні повідомлення на відкритій вкладці.
- Редагування ручних зустрічей, позначення планів як застарілих після календарних змін.
- Модальні вікна з обмеженням висоти, прокруткою форми, нативно-незалежні чекбокси.
- Міграція `0004_manual_day.py`; дані та токени з v0.4 не скидаються.
- 37 успішних автоматизованих тестів; браузерні скриншоти на трьох розмірах екрана.

# Day Builder — Change log

## v0.4.0 (2026-10-11)

- Read-only plan proposal and explicit acceptance endpoints (`/api/plans/preview`, `/api/plans/apply`).
- Optimistic revision check rejects stale calendar and preferences changes with 409 without replacing saved plans.
- Built-in web UI adds a proposal modal with diff and warning sections.
- Calendar OAuth setup wizard and read-only diagnostics endpoint that never exposes credentials.
- React UI supports the preview / explicit confirmation flow (React build unverified here).
- No schema migration required from v0.3; 23 backend tests passing.
- Live OAuth and browser E2E remain unverified.

## v0.3.0 (2026-10-11)

- Optional background calendar polling every 5–60 minutes while FastAPI is running.
- Idempotent event synchronization and per-day stale-plan detection.
- Browser detects external updates; calendar screen shows sync state/errors.
- New Alembic 0003 migration preserves v0.2 data and credentials.
- 18 automated backend tests and separate migration smoke check.
- OAuth end-to-end with live provider accounts and full browser E2E are still unverified.

## v0.2.0 (2026-10-11)

- Google Calendar OAuth Authorization Code + PKCE, read-only Calendar API.
- Microsoft Outlook/Teams OAuth Authorization Code + PKCE, read-only Microsoft Graph CalendarView.
- Local encrypted token vault and access-token refreshing; OAuth state validation.
- Manual per-provider sync over a fixed date window, pagination, event filtering, time zone normalization, and duplicate-free replacement.
- Calendar UI buttons to connect, sync, disconnect; imported meeting source shown; imported meetings protected against local deletion.
- New Alembic 0002 migration preserves existing v0.1 activities, meetings, plans.
- 14 pytest tests, Windows configuration script and calendar setup guide.
- No real provider account authorization or scheduled background sync tested; localhost only.

## v0.1.0 (2026-10-10)

- Local FastAPI + SQLite planning engine, activities, manual meetings, meals, generated plans and no-build web UI.
