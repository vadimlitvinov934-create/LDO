# core/helpers.py
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from config import get_schedule_for, LATE_GRACE_MIN, to_minutes, now_minutes

STATUS_LABELS = {
    "present": "Присутствовал",
    "late": "Опоздал",
    "absent": "Отсутствовал",
    "excused": "Уважительная причина",
    "skip": "Не учитывается",
    "": "—",
}

REASON_LABELS = {
    "sick": "Болезнь",
    "competition": "Соревнования",
    "family": "Семейные обстоятельства",
    "other": "Другое",
    None: "",
}

def parse_date_param(s: Optional[str]) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()

def current_period_index(now_mins: Optional[int] = None, schedule: Optional[List[Dict[str, Any]]] = None) -> int:
    nm = now_mins if now_mins is not None else now_minutes()
    schedule = schedule or get_schedule_for()
    for i, p in enumerate(schedule):
        if to_minutes(p["start"]) <= nm <= to_minutes(p["end"]):
            return i
    return -1

def compute_status(mark_hhmm: Optional[str], period: Dict[str, Any], now_m: Optional[int] = None) -> str:
    """Онлайн-статус сегодня, если в БД нет status."""
    nowm = now_m if now_m is not None else now_minutes()
    start = to_minutes(period["start"])
    end = to_minutes(period["end"])
    late_border = start + LATE_GRACE_MIN
    if not mark_hhmm:
        if nowm < start: return ""
        if nowm <= end: return ""
        return "absent"
    m = to_minutes(mark_hhmm)
    if m <= start: return "present"
    if start < m <= end:
        return "late" if m > late_border else "present"
    return "late"

def compute_status_by_mark(mark_hhmm: Optional[str], period: Dict[str, Any]) -> str:
    """Оффлайн-статус для прошедших дат, если в БД нет status."""
    if not mark_hhmm:
        return "absent"
    start = to_minutes(period["start"])
    end   = to_minutes(period["end"])
    m     = to_minutes(mark_hhmm)
    if m <= start: return "present"
    if start < m <= end:
        return "late" if m > start + LATE_GRACE_MIN else "present"
    return "late"
