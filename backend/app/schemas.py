from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def minutes(value: str) -> int:
    try:
        h, m = map(int, value.split(":"))
    except (ValueError, AttributeError):
        raise ValueError("Час повинен мати формат HH:MM")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Неприпустимий час")
    return h * 60 + m

class Meal(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=80)
    earliest_start: str
    latest_end: str
    duration_minutes: int = Field(ge=15, le=180, multiple_of=15)

    @model_validator(mode="after")
    def validate_window(self):
        start, end = minutes(self.earliest_start), minutes(self.latest_end)
        if start >= end or end - start < self.duration_minutes:
            raise ValueError("Вікно прийому їжі менше за його тривалість")
        return self

class PreferencesIn(BaseModel):
    wake_time: str = "08:00"
    sleep_time: str = "23:30"
    timezone: str = "Europe/Kyiv"
    energy_peak_start: str = "09:00"
    energy_peak_end: str = "12:00"
    meals: list[Meal] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def valid_settings(self):
        if minutes(self.sleep_time) - minutes(self.wake_time) < 60:
            raise ValueError("Час сну має бути пізніше пробудження щонайменше на годину (в межах дати)")
        if minutes(self.energy_peak_end) <= minutes(self.energy_peak_start):
            raise ValueError('Продуктивний проміжок повинен мати додатну тривалість')
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Невідомий часовий пояс")
        keys = [meal.key for meal in self.meals]
        if len(keys) != len(set(keys)):
            raise ValueError("Прийоми їжі повинні мати унікальні ключі")
        return self

class ActivityIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    category: Literal["work", "study", "health", "personal", "leisure"] = "personal"
    duration_minutes: int = Field(ge=15, le=480, multiple_of=15)
    priority: int = Field(default=3, ge=1, le=5)
    required: bool = True
    earliest_start: str = "08:00"
    latest_end: str = "23:00"
    recurrence: Literal["daily", "weekdays", "weekends", "once", "custom"] = "daily"
    target_date: date | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_activity(self):
        if minutes(self.latest_end) - minutes(self.earliest_start) < self.duration_minutes:
            raise ValueError("Завдання не вміщується у вказане часове вікно")
        if self.recurrence == "once" and self.target_date is None:
            raise ValueError("Для разового завдання потрібно вказати дату")
        if self.recurrence != "once" and self.target_date is not None:
            raise ValueError("Дата застосовується тільки до періодичності «Разово»")
        return self

class ActivityOut(ActivityIn):
    model_config = ConfigDict(from_attributes=True)
    id: int

class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    on_date: date
    start_time: str
    end_time: str

    @model_validator(mode="after")
    def valid_window(self):
        if minutes(self.end_time) <= minutes(self.start_time):
            raise ValueError("Подія повинна закінчуватись після початку")
        return self

class EventOut(EventIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str

class PlanGenerate(BaseModel):
    on_date: date

class BlockStatusIn(BaseModel):
    status: Literal["pending", "done", "skipped"]

class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    source_id: int | None
    title: str
    category: str
    start_min: int
    end_min: int
    status: str
    explanation: str
    is_locked: bool = False

class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    on_date: date
    warnings: list[str]
    calendar_stale: bool = False
    blocks: list[BlockOut]

class BlockEditIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    start_min: int = Field(ge=0, le=1439)
    end_min: int = Field(ge=1, le=1440)
    category: Literal["work", "study", "health", "personal", "leisure"] = "personal"
    is_locked: bool = True
    @model_validator(mode="after")
    def check_window(self):
        if self.end_min <= self.start_min or self.end_min - self.start_min > 480:
            raise ValueError("Некоректна тривалість блоку")
        return self

class CustomBlockIn(BlockEditIn):
    on_date: date

class MoveBlockIn(BaseModel):
    on_date: date
    block_id: int
    target_id: int

class LockBlockIn(BaseModel):
    is_locked: bool

class WeekApplyIn(BaseModel):
    monday: date
    revisions: dict[date, str] = Field(min_length=1, max_length=7)

    @field_validator('revisions')
    @classmethod
    def validate_revisions(cls, values):
        if any(len(revision) != 64 or any(c not in '0123456789abcdef' for c in revision) for revision in values.values()):
            raise ValueError('Неправильний формат ревізії розкладу')
        return values

class FocusSessionIn(BaseModel):
    on_date: date
    title: str = Field(min_length=1, max_length=160)
    category: Literal['work','study','health','personal','leisure'] = 'study'
    minutes: int = Field(ge=1, le=180)

class FocusSessionOut(FocusSessionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int

class ReflectionIn(BaseModel):
    mood: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    note: str = Field(default='', max_length=2000)

class ReflectionOut(ReflectionIn):
    model_config = ConfigDict(from_attributes=True)
    on_date: date
