from __future__ import annotations
from datetime import date, datetime, time as dtime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import select
from models import SessionLocal, Student, Attendance, StarostaLock
from core.auth_bp import require_role
from core.permissions import get_starosta_groups
from config import get_schedule_for
from core.helpers import current_period_index

starosta_bp = Blueprint("starosta", __name__, template_folder="../templates")


def _starosta_group() -> str | None:
    fio = (session.get("user") or {}).get("fio", "")
    groups = [g.strip() for g in get_starosta_groups(fio) if g and g.strip()]
    if not groups:
        return None
    # Предполагаем 1 группу на старосту; если больше — возьмём первую
    return groups[0]


@starosta_bp.route("/starosta", methods=["GET"])
@require_role("starosta")
def starosta_form():
    g = _starosta_group()
    if not g:
        flash("Для вашего профиля не назначена группа. Обратитесь к куратору.", "error")
        return render_template(
            "starosta.html",
            students=[],
            schedule=[],
            current_index=None,
            group_code=None,
            locked=True,
        )

    today_d = date.today()
    schedule = get_schedule_for(today_d)
    cur_idx = current_period_index(schedule=schedule)
    if cur_idx is None or cur_idx < 0 or cur_idx >= len(schedule):
        cur_idx = None

    # Получим студентов только своей группы
    with SessionLocal() as s:
        students = (
            s.query(Student)
            .filter(Student.group_code == g)
            .order_by(Student.full_name)
            .all()
        )

        # Проверим блокировку: отправляли ли уже сегодня на эту пару
        locked = False
        period_code = None
        if cur_idx is not None:
            period_code = schedule[cur_idx]["code"]
            lock = (
                s.query(StarostaLock)
                .filter(
                    StarostaLock.date == today_d,
                    StarostaLock.period_code == period_code,
                    StarostaLock.group_code == g,
                )
                .first()
            )
            locked = bool(lock)

    return render_template(
        "starosta.html",
        students=students,
        schedule=schedule,
        current_index=cur_idx,
        group_code=g,
        locked=locked,
        excused_reasons=["sick", "competition", "family", "other"],
    )


@starosta_bp.route("/starosta/submit", methods=["POST"])
@require_role("starosta")
def starosta_submit():
    g = _starosta_group()
    if not g:
        flash("Не назначена группа старосты.", "error")
        return redirect(url_for("starosta.starosta_form"))

    today_d = date.today()
    schedule = get_schedule_for(today_d)
    cur_idx = current_period_index(schedule=schedule)
    if cur_idx is None or cur_idx < 0 or cur_idx >= len(schedule):
        flash("Сейчас нет активной пары для отметки.", "error")
        return redirect(url_for("starosta.starosta_form"))
    period_code = schedule[cur_idx]["code"]

    status = (request.form.get("status") or "").strip()
    if status not in {"present", "absent", "excused"}:
        flash("Выберите статус (был/не был/уважительная).", "error")
        return redirect(url_for("starosta.starosta_form"))
    reason = (request.form.get("reason") or "").strip() if status == "excused" else None

    # Список студентов
    ids = request.form.getlist("student_ids")
    ids = [int(x) for x in ids if str(x).isdigit()]
    if not ids:
        flash("Выберите хотя бы одного студента.", "error")
        return redirect(url_for("starosta.starosta_form"))

    fio = (session.get("user") or {}).get("fio", "")

    with SessionLocal() as s:
        # повторная отправка запрещена
        exists = (
            s.query(StarostaLock)
            .filter(
                StarostaLock.date == today_d,
                StarostaLock.period_code == period_code,
                StarostaLock.group_code == g,
            )
            .first()
        )
        if exists:
            flash("Отметка уже была отправлена для этой пары. Повтор запрещен.", "error")
            return redirect(url_for("starosta.starosta_form"))

        now_t = datetime.now().time()
        # применим статус ко всем выбранным
        for sid in ids:
            st = (
                s.query(Student)
                .filter(Student.id == sid, Student.group_code == g)
                .first()
            )
            if not st:
                continue
            rec = (
                s.query(Attendance)
                .filter(
                    Attendance.date == today_d,
                    Attendance.period_code == period_code,
                    Attendance.student_id == sid,
                )
                .first()
            )
            if not rec:
                rec = Attendance(date=today_d, period_code=period_code, student_id=sid)
                s.add(rec)
            rec.status = status
            rec.reason = reason
            rec.time = now_t

        # создаём блокировку
        lock = StarostaLock(
            date=today_d, period_code=period_code, group_code=g, submitted_by=fio
        )
        s.add(lock)
        s.commit()

    flash("Отметки сохранены и зафиксированы — повторная отправка закрыта.", "success")
    return redirect(url_for("starosta.starosta_form"))