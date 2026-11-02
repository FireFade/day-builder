# Лабораторна робота 2 — скріншотне тестування Day Builder

## Об’єкт тестування

Тести перевіряють основний автономний інтерфейс `web/` у Day Builder 1.0 Beta. Попередній React-прототип у `frontend/` не використовується. П’ять окремих екранів: огляд, мій день, активності, календар і налаштування.

Тестовий HTTP-сервер віддає локальні файли `web/`, а Playwright перехоплює `/api/*` та повертає фікстури. Реальна база даних, OAuth-ключі та Google/Microsoft-акаунти не читаються. Дата заморожена на 2 листопада 2026 року; розмір браузера — 1440 × 1000 CSS-пікселів, масштаб — 1.

## Встановлення

З кореня репозиторію:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-lab.txt
```

Скрипт автоматично використовує Microsoft Edge за типовим шляхом Windows. Якщо Edge недоступний, встановіть Chromium для Playwright:

```powershell
backend\.venv\Scripts\python.exe -m playwright install chromium
```

Можна задати інший виконуваний браузер через змінну середовища `DAY_BUILDER_BROWSER`.

## Запуск скріншотних тестів

```powershell
backend\.venv\Scripts\python.exe -m pytest visual_tests\test_screenshot_pages.py -q
```

Еталони зберігаються у `visual_tests/snapshots/approved/`. Звичайний запуск порівнює поточні зображення з еталонами та зберігає їх у `visual_tests/results/current/`. Поріг відмінності — 0,1% пікселів. Якщо розміри знімків відрізняються, вони доповнюються білим тлом до однакового розміру перед порівнянням.

Щоб свідомо затвердити новий вигляд після перегляду знімків:

```powershell
$env:DAY_BUILDER_UPDATE_BASELINES = "1"
backend\.venv\Scripts\python.exe -m pytest visual_tests\test_screenshot_pages.py -q
Remove-Item Env:DAY_BUILDER_UPDATE_BASELINES
```

Не оновлюйте еталони лише для того, щоб приховати несподівану зміну інтерфейсу.

## Відтворення дефекту

Змінна `DAY_BUILDER_VISUAL_DEFECTS=1` додає CSS перед знімком: переводить сторінку у відтінки сірого, розширює й перефарбовує бічну панель, збільшує заголовок і прибирає заокруглення карток. CSS додається лише в тестовій вкладці браузера; файли `web/` не змінюються.

```powershell
$env:DAY_BUILDER_VISUAL_DEFECTS = "1"
backend\.venv\Scripts\python.exe -m pytest visual_tests\test_screenshot_pages.py -q
Remove-Item Env:DAY_BUILDER_VISUAL_DEFECTS
```

У цьому режимі очікуються п’ять падінь порівняння. Поточні знімки з дефектами зберігаються у `visual_tests/results/defects/`.

## Результат лабораторної

- Створення затверджених еталонів: 5/5 пройшло.
- Три повторні контрольні запуски: 5/5 пройшло в кожному запуску.
- Запуск із CSS-дефектами: 0/5 пройшло; усі п’ять сторінок виявили відмінність.
- Артефакти базової та дефектної серій: по п’ять PNG-зображень.

Скріншот API та параметри `full_page` відповідають офіційній документації Playwright Python: https://playwright.dev/python/docs/screenshots
