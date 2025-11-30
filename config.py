# config.py
from __future__ import annotations
from datetime import datetime, date
import os
from pathlib import Path

# ==== БЛОК НАСТРОЕК РАСПИСАНИЯ / ВРЕМЕНИ ====

LATE_GRACE_MIN: int = 0  # льгота опоздания в минутах


def today_key(dt: datetime | None = None) -> str:
    d = dt or datetime.now()
    return d.strftime("%Y-%m-%d")


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def now_minutes(dt: datetime | None = None) -> int:
    d = dt or datetime.now()
    return d.hour * 60 + d.minute


# ПОНЕДЕЛЬНИК — с классным часом
MONDAY = [
    {"code": "kh", "title": "Кл. час", "start": "07:45", "end": "08:05"},
    {"code": "p1", "title": "Пара 1", "start": "08:10", "end": "09:40"},
    {"code": "p2", "title": "Пара 2", "start": "09:50", "end": "11:20"},
    {"code": "p3", "title": "Пара 3", "start": "11:40", "end": "13:10"},
    {"code": "p4", "title": "Пара 4", "start": "13:15", "end": "14:45"},
    {"code": "p5", "title": "Пара 5", "start": "15:05", "end": "16:35"},
    {"code": "p6", "title": "Пара 6", "start": "16:40", "end": "18:10"},
    {"code": "p7", "title": "Пара 7", "start": "18:15", "end": "19:45"},
]

# ВТ–ПТ
TUE_FRI = [
    {"code": "p1", "title": "Пара 1", "start": "07:45", "end": "09:15"},
    {"code": "p2", "title": "Пара 2", "start": "09:25", "end": "10:55"},
    {"code": "p3", "title": "Пара 3", "start": "11:15", "end": "12:45"},
    {"code": "p4", "title": "Пара 4", "start": "12:50", "end": "14:20"},
    {"code": "p5", "title": "Пара 5", "start": "14:40", "end": "16:10"},
    {"code": "p6", "title": "Пара 6", "start": "16:15", "end": "17:45"},
    {"code": "p7", "title": "Пара 7", "start": "17:50", "end": "19:20"},
]

SATURDAY: list[dict] = []
SUNDAY: list[dict] = []

WEEKLY_SCHEDULE = {
    0: MONDAY,
    1: TUE_FRI,
    2: TUE_FRI,
    3: TUE_FRI,
    4: TUE_FRI,
    5: SATURDAY,
    6: SUNDAY,
}


def get_schedule_for(dt: date | datetime | None = None) -> list[dict]:
    d = dt or datetime.now()
    wd = d.weekday()
    return WEEKLY_SCHEDULE.get(wd, [])


# ==== БЛОК КОНФИГА FLASK-ПРИЛОЖЕНИЯ ====

BASE_DIR = Path(__file__).resolve().parent

# Можно переопределить через переменные окружения:
#   SECRET_KEY, DATABASE_URL, FLASK_DEBUG
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-ldo-secret-key")
# SQLite-файл ldo.db рядом с приложением
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'ldo.db').as_posix()}",
)


class Config:
    """
    Конфиг для Flask: app.config.from_object(Config)
    """

    # базовые настройки Flask
    SECRET_KEY = SECRET_KEY
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_PERMANENT = True

    # если где-то нужно брать строку подключения из app.config
    DATABASE_URL = DATABASE_URL
