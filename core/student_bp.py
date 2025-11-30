# core/routes_student.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date, datetime, timedelta
from models import SessionLocal, Student, Attendance
from core.auth_bp import require_role
from config import get_schedule_for, today_key
from core.helpers import current_period_index

student_bp = Blueprint("student_bp", __name__)

def _week_range(center: date):
    start = center - timedelta(days=center.weekday())  # понедельник
    return [start + timedelta(days=i) for i in range(7)]

@student_bp.route("/student")
@require_role("student")
def dashboard():
    fio = session.get("user", {}).get("fio")
    if not fio:
        flash("Сессия недействительна", "error")
        return redirect(url_for("auth_bp.login"))

    today = date.today()
    schedule_today = get_schedule_for(today)

    with SessionLocal() as s:
        st = s.query(Student).filter(Student.full_name == fio).first()
        if not st:
            flash("Студент не найден в базе", "error")
            return redirect(url_for("auth_bp.logout"))

        week_days = _week_range(today)
        recs = (
            s.query(Attendance)
             .filter(Attendance.student_id == st.id,
                     Attendance.date.in_(week_days))
             .all()
        )

    # группируем статусы по датам и парам
    week_map = {d: {} for d in week_days}  # {date: {p1: status, ...}}
    for r in recs:
        week_map.setdefault(r.date, {})[r.period_code] = r.status or ""

    # приводим к удобному виду для шаблона
    week_view = []
    for d in week_days:
        week_view.append({
            "date": d,
            "date_text": d.strftime("%Y-%m-%d"),
            "items": week_map.get(d, {})
        })

    return render_template(
        "student.html",
        fio=fio,
        today=today_key(),
        schedule_today=schedule_today,
        week=week_view
    )

@student_bp.route("/student/checkin", methods=["POST"])
@require_role("student")
def student_checkin():
    fio = session.get("user", {}).get("fio")
    if not fio:
        flash("Сессия недействительна", "error")
        return redirect(url_for("auth_bp.login"))

    today = date.today()
    now = datetime.now().time()
    schedule = get_schedule_for(today)
    idx = current_period_index(schedule=schedule)

    if idx is None:
        flash("Сейчас нет текущей пары, отметка не сохранена.", "error")
        return redirect(url_for("student_bp.dashboard"))

    period_code = schedule[idx]["code"]

    with SessionLocal() as s:
        st = s.query(Student).filter(Student.full_name == fio).first()
        if not st:
            flash("Студент не найден в базе", "error")
            return redirect(url_for("auth_bp.logout"))

        rec = (
            s.query(Attendance)
             .filter(Attendance.date == today,
                     Attendance.period_code == period_code,
                     Attendance.student_id == st.id)
             .first()
        )
        if not rec:
            rec = Attendance(
                date=today,
                period_code=period_code,
                time=now,
                student_id=st.id,
                status="present",
                reason=None
            )
            s.add(rec)
        else:
            rec.time = now
            rec.status = "present"
            rec.reason = None
        s.commit()

    flash("Отметка «Я пришёл» сохранена", "success")
    return redirect(url_for("student_bp.dashboard"))
