# core/permissions.py
from typing import List
from models import SessionLocal, Student
from sqlalchemy import func

# Карта кураторов -> список их групп (строго те же строки, что в students.group_code)
CURATOR_GROUPS = {
    "Султангазинова Диана Сериковна": ["PO-115", "PO-393"],  # при необходимости убери
    "Брусенко Владислав Сергеевич": ["PO-175", "PO-323"],
}

def get_curator_groups(curator_fio: str) -> List[str]:
    """Возвращает список групп, за которые отвечает данный куратор."""
    return CURATOR_GROUPS.get(curator_fio, [])

def student_in_curator_scope(curator_fio: str, student_id: int) -> bool:
    """Проверяем, что студент относится к одной из групп данного куратора."""
    groups = get_curator_groups(curator_fio)
    if not groups:
        return False
    with SessionLocal() as s:
        st = s.query(Student).filter(Student.id == student_id).first()
        if not st:
            return False
        return (st.group_code or "") in groups


# Карта старост -> список их групп
STAROSTA_GROUPS = {
    "Староста ПО175": ["PO-175"],
}

def get_starosta_groups(starosta_fio: str) -> list[str]:
    """Список групп, за которые отвечает староста."""
    return STAROSTA_GROUPS.get(starosta_fio, [])

def student_in_starosta_scope(starosta_fio: str, student_id: int) -> bool:
    """Проверяем, что студент относится к группе старосты."""
    groups = get_starosta_groups(starosta_fio)
    if not groups:
        return False
    with SessionLocal() as s:
        st = s.query(Student).filter(Student.id == student_id).first()
        if not st:
            return False
        return (st.group_code or "") in groups

HEAD_PREFIXES = {
    # "ФИО заведующей": ["PO-"],
    "Иванова Галина Петровна": ["PO-"],
}

def get_head_allowed_prefixes(head_fio: str) -> list[str]:
    return HEAD_PREFIXES.get(head_fio, [])

def head_list_groups_for_prefixes(prefixes: list[str]) -> list[str]:
    """Вернуть список групп из БД, начинающихся с указанных префиксов."""
    if not prefixes:
        return []
    with SessionLocal() as s:
        q = s.query(func.trim(Student.group_code)).filter(Student.group_code.isnot(None))
        # склеиваем условия по префиксам
        cond = None
        for pfx in prefixes:
            like_expr = f"{pfx}%"
            part = Student.group_code.like(like_expr)
            cond = part if cond is None else (cond | part)
        if cond is not None:
            q = q.filter(cond)
        groups = sorted({(g or "").strip() for (g,) in q.distinct().all() if (g or "").strip()})
        return groups

def head_group_allowed(head_fio: str, group_code: str) -> bool:
    """Можно ли заведующей видеть конкретную группу."""
    prefixes = get_head_allowed_prefixes(head_fio)
    if not prefixes:
        return False
    g = (group_code or "").strip()
    return any(g.startswith(p) for p in prefixes)