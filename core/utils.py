# core/utils.py
STATUS_LABELS = {
    "present": "Присутствовал",
    "late": "Опоздал",
    "absent": "Отсутствовал",
    "excused": "Уважительная причина",
    "skip": "Пары нет",
}

def status_label(code: str) -> str:
    """Возвращает русский текст статуса посещаемости."""
    return STATUS_LABELS.get(code, code)
