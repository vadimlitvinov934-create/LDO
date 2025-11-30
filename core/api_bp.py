from flask import Blueprint, jsonify, request, session
from models import SessionLocal, Student, Attendance
from datetime import datetime, date
from config import get_schedule_for, to_minutes, LATE_GRACE_MIN
from core.helpers import current_period_index
from core.permissions import student_in_curator_scope

api_bp = Blueprint("api_bp", __name__)

# Маршруты сканера (/scanner, /scan) и генерации QR (/qr/...) УДАЛЕНЫ.

@api_bp.route("/api/checkin", methods=["POST"])
def api_checkin():
    """
    API для отметки посещаемости.
    Принимает JSON: {"uid": "...", "period_code": "..."}
    """
    data = request.get_json(silent=True) or {}
    uid = (data.get("uid") or "").strip()
    period_code = (data.get("period_code") or "").strip() or None

    today_d = date.today()
    now_t = datetime.now().time()
    schedule = get_schedule_for(today_d)

    with SessionLocal() as s:
        st = s.query(Student).filter_by(uid=uid).first()
        if not st:
            return jsonify({"ok": False, "error": "Студент не найден"}), 404

        # Если запрос делает залогиненный КУРАТОР — запретить отмечать «чужих»
        user = session.get("user") or {}
        if user.get("role") == "curator":
            if not student_in_curator_scope(user.get("fio", ""), st.id):
                return jsonify({"ok": False, "error": "not_allowed"}), 403

        if not period_code:
            idx = current_period_index(schedule=schedule)
            if idx < 0:
                return jsonify({"ok": False, "error": "Сейчас нет активной пары."}), 400
            period_code = schedule[idx]["code"]

        rec = s.query(Attendance).filter_by(date=today_d, period_code=period_code, student_id=st.id).first()
        if not rec:
            rec = Attendance(date=today_d, period_code=period_code, time=now_t, student_id=st.id)
            s.add(rec)
        else:
            rec.time = now_t
        s.commit()

        p = next((pp for pp in schedule if pp["code"] == period_code), None)
        status = "present"
        if p:
            start_m, end_m = to_minutes(p["start"]), to_minutes(p["end"])
            t_m = now_t.hour*60 + now_t.minute
            if t_m <= start_m + LATE_GRACE_MIN: status = "present"
            elif t_m <= end_m: status = "late"
            else: status = "absent"

        return jsonify({
            "ok": True,
            "student": {"id": st.id, "uid": st.uid, "name": st.full_name},
            "period": period_code,
            "time": now_t.strftime("%H:%M"),
            "status": status
        }), 200