# Day Builder v0.3 — QA verification

## Перевірено у середовищі створення (Linux)

- `python -m pytest -q` у `backend/`: 18/18 PASS.
- `node --check web/app.js`: PASS, синтаксис коректний.
- `python -m compileall -q backend/app`: PASS.
- Alembic SQLite upgrade 0002 → 0003: PASS, збережені план та календарна зустріч не зникли.
- FastAPI, запущений локально через Uvicorn, відповів `GET /api/health` статусом 200.
- Додані, видалені, змінені зустрічі роблять відповідний збережений план застарілим; повторна синхронізація без змін не зачіпає існуючі event id.
- Помилка/некоректні дані провайдера не видаляють раніше імпортовані події.

## Не перевірено

- End-to-end OAuth з реальними Google / Microsoft credentials.
- Повне браузерне E2E — Chromium у середовищі викликав `net::ERR_BLOCKED_BY_ADMINISTRATOR` при переході на localhost. Це обмеження тестового середовища; не вважаємо E2E пройденим.
- Реальне 15-хвилинне виконання background poll із живими календарями.
- Запуск Windows PowerShell на реальному Windows комп'ютері.
- React/NPM збірка, Docker збірка, production security review.

Це локальний MVP без авторизації користувачів — не публікувати у мережу.
