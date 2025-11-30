# core/routes_checkin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import SessionLocal, Student, Attendance
from datetime import date, datetime
from core.helpers import current_period_index
from config import get_schedule_for, today_key
from core.auth_bp import require_role
from .permissions import get_curator_groups, student_in_curator_scope
from sqlalchemy import func

checkin_bp = Blueprint("checkin_bp", __name__)

# ---------- ВСПОМОГАТЕЛЬНОЕ ----------
VALID_STATUSES = ("present", "late", "absent", "excused")

def _upsert_attendance(s, *, d, student_id, period_code, status, reason, now_time):
    """Создаёт/обновляет отметку посещаемости на дату/пару/студента."""
    rec = (
        s.query(Attendance)
        .filter(
            Attendance.date == d,
            Attendance.period_code == period_code,
            Attendance.student_id == student_id,
        )
        .first()
    )
    if not rec:
        rec = Attendance(
            date=d,
            period_code=period_code,
            time=now_time,
            student_id=student_id,
            status=status,
            reason=reason,
        )
        s.add(rec)
    else:
        rec.time = now_time
        rec.status = status
        rec.reason = reason

# ---------- СТРАНИЦА ----------
@checkin_bp.route("/checkin")
@require_role("curator")
def checkin_page():
    d = date.today()
    schedule = get_schedule_for(d)

    # текущий куратор и его группы
    fio = (session.get("user") or {}).get("fio", "")
    curator_groups = [g.strip() for g in (get_curator_groups(fio) or []) if g and g.strip()]

    # выбранная группа из параметра ?g=PO-175 (или пусто = все группы куратора)
    selected_group = (request.args.get("g") or "").strip()

    with SessionLocal() as s:
        # базовый фильтр: только студенты из групп куратора
        q = s.query(Student)
        if curator_groups:
            q = q.filter(func.trim(Student.group_code).in_(curator_groups))
        else:
            q = q.filter(Student.id == -1)  # если у куратора не настроены группы — пусто

        # список доступных групп по фактическим данным
        groups_available = [
            g for (g,) in s.query(func.trim(Student.group_code))
                           .filter(func.trim(Student.group_code).in_(curator_groups))
                           .distinct()
                           .order_by(func.trim(Student.group_code))
        ]

        # если выбрана конкретная группа — дополнительно сузим
        if selected_group:
            if selected_group in curator_groups:
                q = q.filter(func.trim(Student.group_code) == selected_group)
            else:
                q = q.filter(Student.id == -1)

        students = q.order_by(Student.full_name).all()

    cur_idx = current_period_index(schedule=schedule)

    return render_template(
        "checkin.html",
        students=students,
        schedule=schedule,
        current_index=cur_idx,
        today=today_key(),
        valid_statuses=VALID_STATUSES,
        excused_reasons=["sick", "competition", "family", "other"],
        # новое:
        groups_available=groups_available,
        selected_group=selected_group,
    )

# ---------- ОДИНОЧНАЯ (наследие: одна запись) ----------
@checkin_bp.route("/checkin", methods=["POST"])
@require_role("curator")
def do_checkin():
    """Старый режим: одна запись (оставляем совместимость)."""
    try:
        student_id = int(request.form.get("student_id") or "0")
    except ValueError:
        student_id = 0
    period_code = (request.form.get("period_code") or "").strip()
    status = (request.form.get("status") or "").strip()
    reason = (request.form.get("reason") or "").strip() if status == "excused" else None

    if not student_id or not period_code or status not in VALID_STATUSES:
        flash("Проверьте выбор: студент, пара, статус", "error")
        return redirect(url_for("checkin_bp.checkin_page"))

    # защита: куратор не может отмечать чужих студентов
    user = session.get("user") or {}
    if user.get("role") == "curator" and not student_in_curator_scope(user.get("fio", ""), student_id):
        flash("Недостаточно прав для этого студента", "error")
        return redirect(url_for("checkin_bp.checkin_page"))

    today_d = date.today()
    now_t = datetime.now().time()
    with SessionLocal() as s:
        st = s.query(Student).filter(Student.id == student_id).first()
        if not st:
            flash("Студент не найден", "error")
            return redirect(url_for("checkin_bp.checkin_page"))
        _upsert_attendance(
            s,
            d=today_d,
            student_id=student_id,
            period_code=period_code,
            status=status,
            reason=reason,
            now_time=now_t,
        )
        s.commit()
    flash("✅ Отметка сохранена", "ok")
    return redirect(url_for("checkin_bp.checkin_page"))

# ---------- МАССОВО: несколько студентов × несколько пар ----------
@checkin_bp.route("/checkin/bulk", methods=["POST"])
@require_role("curator")
def do_checkin_bulk():
    today_d = date.today()
    now_t = datetime.now().time()

    # студенты
    all_students_flag = request.form.get("all_students") == "1"
    sel_student_ids = request.form.getlist("student_ids")
    # пары
    all_periods_flag = request.form.get("all_periods") == "1"
    sel_periods = request.form.getlist("period_codes")
    # статус
    status = (request.form.get("status") or "").strip()
    reason = (request.form.get("reason") or "").strip() if status == "excused" else None
    # выбранная группа (скрытое поле из формы)
    selected_group = (request.form.get("g") or "").strip()

    if status not in VALID_STATUSES:
        flash("Выберите корректный статус", "error")
        return redirect(url_for("checkin_bp.checkin_page", g=selected_group))

    user = session.get("user") or {}
    fio = user.get("fio", "")

    with SessionLocal() as s:
        if all_students_flag:
            # если фильтр по группе задан — берём только её
            if selected_group:
                q = s.query(Student).filter(func.trim(Student.group_code) == selected_group)
            else:
                curator_groups = [g.strip() for g in (get_curator_groups(fio) or []) if g and g.strip()]
                q = s.query(Student)
                if curator_groups:
                    q = q.filter(func.trim(Student.group_code).in_(curator_groups))
                else:
                    q = q.filter(Student.id == -1)
            students = q.order_by(Student.full_name).all()
            student_ids = [st.id for st in students]
        else:
            try:
                candidate_ids = [int(x) for x in sel_student_ids]
            except ValueError:
                candidate_ids = []
            # защита: только те, кто в зоне куратора
            student_ids = [sid for sid in candidate_ids if student_in_curator_scope(fio, sid)]

        if not student_ids:
            flash("Не выбраны студенты", "error")
            return redirect(url_for("checkin_bp.checkin_page", g=selected_group))

        # пары
        schedule = get_schedule_for(today_d)
        if all_periods_flag:
            period_codes = [p["code"] for p in schedule if p["code"].startswith("p")]
        else:
            period_codes = [p for p in sel_periods if p.startswith("p")]
        if not period_codes:
            flash("Не выбраны пары", "error")
            return redirect(url_for("checkin_bp.checkin_page", g=selected_group))

        for sid in student_ids:
            for pc in period_codes:
                _upsert_attendance(
                    s,
                    d=today_d,
                    student_id=sid,
                    period_code=pc,
                    status=status,
                    reason=reason,
                    now_time=now_t,
                )
        s.commit()

    flash(f"✅ Сохранены отметки: {len(student_ids)} студент(ов) × {len(period_codes)} пар(ы)", "ok")
    # сохраняем выбранную группу после POST
    return redirect(url_for("checkin_bp.checkin_page", g=selected_group))

# ---------- БЫСТРО: клик по карточке → статус на ТЕКУЩУЮ пару (AJAX) ----------
@checkin_bp.route("/checkin/quick", methods=["POST"])
@require_role("curator")
def do_checkin_quick():
    """AJAX: выставить статус одному студенту на текущую пару (из карточки)."""
    try:
        student_id = int(request.form.get("student_id") or "0")
    except ValueError:
        student_id = 0
    status = (request.form.get("status") or "").strip()
    reason = (request.form.get("reason") or "").strip() if status == "excused" else None

    if not student_id or status not in VALID_STATUSES:
        return jsonify({"ok": False, "error": "bad params"}), 400

    # защита: куратор не может отмечать чужих студентов
    user = session.get("user") or {}
    if user.get("role") == "curator" and not student_in_curator_scope(user.get("fio", ""), student_id):
        return jsonify({"ok": False, "error": "not_allowed"}), 403

    today_d = date.today()
    now_t = datetime.now().time()
    schedule = get_schedule_for(today_d)
    idx = current_period_index(schedule=schedule)
    if idx is None or idx < 0:
        return jsonify({"ok": False, "error": "no current period"}), 400
    period_code = schedule[idx]["code"]

    with SessionLocal() as s:
        st = s.query(Student).filter(Student.id == student_id).first()
        if not st:
            return jsonify({"ok": False, "error": "student not found"}), 404
        _upsert_attendance(
            s,
            d=today_d,
            student_id=student_id,
            period_code=period_code,
            status=status,
            reason=reason,
            now_time=now_t,
        )
        s.commit()
    return jsonify({"ok": True, "period_code": period_code, "status": status})
