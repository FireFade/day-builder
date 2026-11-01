# Day Builder v0.4 — підключення Google Calendar і Outlook/Teams (Windows)

**Важливо:** реальне OAuth-підключення не можна протестувати без ваших власних OAuth credentials. Їх **не надсилайте у чат і не публікуйте**. Налаштуйте секрети локально у `.env`. Ця версія призначена тільки для `localhost`, **не виставляйте порт 8000 у відкритий інтернет**.

## 0. Базовий запуск

1. Розпакуйте архів, запустіть PowerShell у папці `day-builder`.
2. Виконайте `powershell -ExecutionPolicy Bypass -File .\start.ps1`.
3. Відкрийте `http://localhost:8000/` → **Календар**. Якщо OAuth ще не налаштований, з'явиться «Не налаштовані OAuth credentials».
4. Закрийте сервер Ctrl+C, заповніть `.env`, запустіть команду повторно.

## 1. Google Calendar

1. Увійдіть до [Google Cloud Console](https://console.cloud.google.com/) та створіть проект (або оберіть наявний).
2. У **APIs & Services → Library** знайдіть **Google Calendar API** і увімкніть його.
3. Налаштуйте **Google Auth Platform → Branding / Audience / Data Access** (назви розділів можуть змінюватися). Якщо обрали External + Testing, додайте свою адресу до **Test users**.
4. Додайте OAuth permission scope: `https://www.googleapis.com/auth/calendar.readonly`. Він дає читати список календарів і події без права редагування.
5. У **Clients → Create Client → Web application** створіть OAuth client з **Authorized redirect URI**:

   `http://localhost:8000/api/integrations/google/callback`

6. Скопіюйте `Client ID` та `Client Secret` у `.env`:

   ```dotenv
   GOOGLE_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=...
   ```

7. Запустіть Day Builder, відкрийте **Календар → Підключити Google Calendar**, пройдіть згоду Google, натисніть **Синхронізувати**.
8. Поверніться до **Мій день → Побудувати день**, перевірте пропозицію і натисніть **Застосувати план**.

**Google Testing:** токени для зовнішнього тестового застосунку з calendar scopes можуть потребувати повторного підключення (у тестовому режимі refresh token часто має 7-денний строк). Для широкого публічного використання Google може вимагати верифікацію OAuth-застосунку.

Офіційні джерела: [Google OAuth для вебзастосунків](https://developers.google.com/identity/protocols/oauth2/web-server), [OAuth дозволи Calendar](https://developers.google.com/workspace/calendar/api/auth).

## 2. Microsoft Outlook / Teams через Microsoft Graph

1. Увійдіть до [Microsoft Entra admin center](https://entra.microsoft.com/) → **Identity → Applications → App registrations → New registration**.
2. Оберіть тип підтримуваних облікових записів. Для **Microsoft personal + work/school** вкажіть відповідний multi-tenant тип; для тільки корпоративного — single tenant.
3. Platform: **Web**, Redirect URI:

   `http://localhost:8000/api/integrations/microsoft/callback`

4. У **API permissions → Microsoft Graph → Delegated permissions** додайте **Calendars.Read**. Застосунок також запитує `offline_access` для поновлення доступу.
5. У **Certificates & secrets → New client secret** створіть секрет і одразу скопіюйте його **Value** (не Secret ID).
6. Скопіюйте Application (client) ID, налаштуйте `.env`:

   ```dotenv
   MICROSOFT_CLIENT_ID=...
   MICROSOFT_CLIENT_SECRET=...
   MICROSOFT_TENANT_ID=common
   ```

   Для застосунку тільки вашої організації замініть `common` на **Directory (tenant) ID**.

7. Перезапустіть сервер → **Календар → Підключити Outlook / Teams** → пройдіть авторизацію → **Синхронізувати** → **Побудувати день** → **Застосувати план**.

**Робочий Microsoft 365:** організація може забороняти підключення сторонніх застосунків; тоді потрібна згода адміністратора. Teams-зустрічі імпортуються **як зустрічі з Outlook/Microsoft 365 календаря**, без окремого Teams permission.

Офіційні джерела: [Microsoft delegated OAuth](https://learn.microsoft.com/en-us/graph/auth-v2-user), [Graph calendarView](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0), [Microsoft redirect URI](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url).

## 3. Що вже працює / обмеження

- **Працює у коді:** OAuth state + PKCE, зашифроване зберігання access/refresh токенів (Fernet), оновлення access токенів, ручний імпорт календарів з пагінацією, розгортання повторюваних подій сервісом провайдера, переприв'язка до локального часового поясу, видалення імпортованих подій при відключенні.
- **Не реалізовано:** webhooks/delta sync, вибір окремих календарів, декілька облікових записів одного провайдера, event diff-історія, public user auth, мобільні push.
- **Часова модель MVP:** розклад оперує локальним часом `HH:MM` одного дня, події до кінця дня обрізаються до `23:59`; абсолютні UTC-часи не зберігаються, тому складні DST/fold сценарії потребують розширення схеми перед production.
- **Безпека:** ключ шифрування створюється в `backend/.secrets/calendar.key` (не видаляйте його, інакше вже збережені токени стане неможливо розшифрувати). Він знаходиться на тому самому комп'ютері, що й БД — це захист від випадкового перегляду токенів у файлі БД, **не** захист від користувача/шкідливого ПЗ, що має доступ до всього комп'ютера. Не зберігайте `.env` або ключ у Git/хмарних публічних архівах.
- **Локальна розробка:** вбудований вебсервер bind `127.0.0.1`. Для SaaS потрібні автентифікація, авторизація, ізоляція даних, HTTPS, безпечне керування ключами, аудит, політика зберігання даних і перевірка OAuth app.

## 4. Діагностика

- **Google error `redirect_uri_mismatch`** — перевірте, чи URI записаний точно як у п. 1, із `localhost` і портом 8000.
- **Google `access_denied`** — перевірте Test users / область дозволів / стан consent screen.
- **Microsoft `AADSTS...`** — перевірте вибрані Supported account types, Tenant ID, реєстрацію Web redirect та політику admin consent.
- **Підключено, але немає подій** — виберіть дату в інтерфейсі, синхронізуйте; імпорт охоплює 2 дні **до** обраної та 14 днів **після** неї. Події з позначкою Free не блокують час.
- **Не оновлюється план** — після синхронізації натисніть **Побудувати день**, перевірте пропозицію й натисніть **Застосувати план**.
- **Перевірити API:** `http://localhost:8000/docs` → `GET /api/integrations`. Не публікуйте логів із `code`, `state`, `.env` або токенами.

## 5. Автоматичне оновлення календарів (v0.3)

У `.env` встановіть:

```dotenv
DAYBUILDER_AUTO_SYNC=1
DAYBUILDER_SYNC_INTERVAL_SECONDS=900
```

Перезапустіть `start.ps1`. Після запуску сервер починає опитування приблизно через 8 секунд, потім кожні 15 хв. Для вимкнення поставте `DAYBUILDER_AUTO_SYNC=0`. У «Календарі» показано стан інтеграції, час останнього успішного оновлення та код помилки. Відкритий браузер перевіряє оновлення кожну хвилину.

Якщо змінено календарну зустріч, Day Builder **лише позначає** відповідний збережений план як застарілий. Для нового розкладу натисніть **«Побудувати день»**. Це спеціально зроблено для захисту вже погоджених завдань.

Цей режим працює **лише поки локальний Python сервер запущений**. Для синхронізації після виходу з програми потрібна окрема серверна інфраструктура або автозапуск у Windows (не входить у v0.3). Немає push-повідомлень у згорнутий браузер.

Актуальні офіційні джерела: [Google Events API](https://developers.google.com/workspace/calendar/api/v3/reference/events/list), [Microsoft Graph calendarView](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0).

## 6. Майстер підключення у v0.4

На вкладці «Календар» з'явився майстер із **локальною перевіркою** `GET /api/integrations/diagnostics`. Він показує, які саме `GOOGLE_*` і `MICROSOFT_*` змінні не заповнені, та точні redirect URI. **Не розкриває Client ID, Client Secret або access/refresh tokens.**

Послідовність: створити Web OAuth application в адміністративній консолі → вказати URI, показаний у майстрі → заповнити `.env` → перезапустити `start.ps1` → натиснути «Перевірити» → «Підключити» → «Синхронізувати» → «Побудувати день» → «Застосувати план».

**Важливо:** «Перевірити» лише визначає, чи є налаштування і чи зберігається стан підключення; це **не** доказ справності віддаленого OAuth. Робочі Microsoft 365 акаунти можуть потребувати admin consent. Реальна авторизація й синхронізація перевіряються тільки після згоди власника акаунта у браузері.
