# Лабораторна робота 3 — BDD сценарії Day Builder

## Окремий тестовий набір

Каталог `bdd_tests/` містить Gherkin-файли, pytest-bdd визначення кроків і власну тестову фікстуру. Сценарії перевіряють застосунок на інтеграційному рівні через FastAPI TestClient; для кожного сценарію створюється окрема тимчасова SQLite-база. Продуктивна база, Google OAuth та календарні облікові дані не використовуються.

## Функціональності

- `features/activities.feature` — створення валідної активності та відхилення активності, що не вміщується у часовий інтервал.
- `features/planning.feature` — перегляд і підтвердження актуальної пропозиції плану; відхилення застарілої пропозиції після зміни даних.
- `features/inbox.feature` — збереження вхідного завдання, перетворення його на активність та захист від повторного планування.

Усього автоматизовано шість сценаріїв у трьох Feature-файлах.

## Запуск

З кореня репозиторію у PowerShell:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-lab.txt
backend\.venv\Scripts\python.exe -m pytest bdd_tests -q
```

BDD набір можна також запускати через інше середовище Python після встановлення залежностей з `backend/requirements-lab.txt`. Константа дати у сценаріях — `2026-11-03`, тому приклади розкладу відтворюються однаково.

Для сумісності версія pytest обмежена гілкою 8.x: поточний pytest-bdd використовує pytest fixture-manager hook, який змінений у pytest 9.

## Розташування реалізації

- Gherkin: `bdd_tests/features/*.feature`
- Кроки: `bdd_tests/test_bdd_features.py`
- SQLite/TestClient фікстура: `bdd_tests/conftest.py`
- Залежність: `pytest-bdd` у `backend/requirements-lab.txt`
