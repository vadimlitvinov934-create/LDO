# core/curator_bp.py
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from core.auth_bp import require_role
from core.permissions import get_curator_groups
from core.head_bp import (
    _parse_day,
    _month_range,
    _semester_range,
    _load_students,
    _load_day_attendance,
    _load_skips_for_day,
    _attendance_stats,
    _detailed_student_table,
)

curator_bp = Blueprint("curator_bp", __name__, url_prefix="/curator")


@curator_bp.route("/")
@require_role("curator")
def choose_group():
    """Выбор группы для куратора."""
    user = session.get("user") or {}
    fio = user.get("fio", "")

    groups = get_curator_groups(fio)

    if not groups:
        flash(
            "Для вашего профиля не настроены группы куратора. Обратитесь к администратору.",
            "error",
        )
        return render_template(
            "curator_groups.html",
            groups=[],
            title="Куратор — выбор группы",
        )

    return render_template(
        "curator_groups.html",
        groups=groups,
        title="Куратор — выбор группы",
    )


@curator_bp.route("/group")
@require_role("curator")
def group_view():
    """
    Страница куратора по конкретной группе.

    Показывает:
    - фильтр по дате и режиму (день / месяц / семестр),
    - таблицу "Посещаемость по студентам" (как у заведующей).
    """
    user = session.get("user") or {}
    fio = user.get("fio", "")

    g = (request.args.get("g") or "").strip()
    if not g:
        return redirect(url_for("curator_bp.choose_group"))

    # проверяем, что группа входит в зону ответственности куратора
    groups = get_curator_groups(fio)
    if g not in groups:
        flash("Эта группа не входит в вашу зону ответственности.", "error")
        return redirect(url_for("curator_bp.choose_group"))

    # фильтры
    day = _parse_day(request.args.get("day"))
    mode = (request.args.get("mode") or "day")  # day|month|semester

    if mode == "month":
        start, end = _month_range(day)
    elif mode == "semester":
        start, end = _semester_range(day)
    else:
        start = end = day

    students = _load_students(g)
    day_map = _load_day_attendance(g, day) if mode == "day" else {}
    skips = _load_skips_for_day(g, day)
    stats = _attendance_stats(g, start, end)
    detail = _detailed_student_table(g, start, end)

    return render_template(
        "curator_group.html",
        group=g,
        day=day,
        mode=mode,
        students=students,
        day_map=day_map,   # пригодится, если захотим добавить мини-журнал
        skips=skips,
        stats=stats,
        detail=detail,     # детальная табличка по студентам
        start=start,
        end=end,
        today=date.today(),
    )
