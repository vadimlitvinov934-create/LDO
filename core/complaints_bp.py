# core/routes_complaints.py
from flask import Blueprint, request, jsonify, render_template, session
from datetime import datetime
from queue import Queue
from threading import Lock
import json

from models import SessionLocal
from models import Complaint  # см. класс ниже (п.4)
from core.auth_bp import require_role

complaints_bp = Blueprint("complaints_bp", __name__)

# ---- простейший broadcaster для SSE ----
_listeners = []
_lock = Lock()

def _subscribe():
    q = Queue()
    with _lock:
        _listeners.append(q)
    return q

def _publish(payload: dict):
    with _lock:
        lst = list(_listeners)
    for q in lst:
        q.put(payload)

@complaints_bp.route("/api/complaints", methods=["POST"])
@require_role("starosta")
def create_complaint():
    data = {
        "target_name": (request.form.get("target_name") or "").strip(),
        "period_index": int(request.form.get("period_index") or 0),
        "reason": (request.form.get("reason") or "").strip(),
        "from_name": session.get("user", {}).get("fio", "Староста"),
        "from_role": "starosta",
        "created_at": datetime.utcnow(),
        "status": "new",
    }
    if not data["target_name"] or not (1 <= data["period_index"] <= 7) or not data["reason"]:
        return jsonify({"ok": False, "error": "Заполните все поля"}), 400

    with SessionLocal() as s:
        c = Complaint(
            target_name=data["target_name"],
            period_index=data["period_index"],
            reason=data["reason"],
            from_role=data["from_role"],
            from_name=data["from_name"],
            created_at=data["created_at"],
            status=data["status"],
        )
        s.add(c)
        s.commit()
        s.refresh(c)

        payload = {
            "id": c.id,
            "target_name": c.target_name,
            "period_index": c.period_index,
            "reason": c.reason,
            "from_role": c.from_role,
            "from_name": c.from_name,
            "created_at": c.created_at.isoformat() + "Z",
            "status": c.status,
        }
        _publish(payload)

    return jsonify({"ok": True, "id": c.id})

@complaints_bp.route("/complaints")
@require_role("curator")
def complaints_page():
    with SessionLocal() as s:
        items = s.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return render_template("complaints.html", items=items)

@complaints_bp.route("/complaints/stream")
@require_role("curator")
def complaints_stream():
    def event_stream():
        q = _subscribe()
        try:
            # отправим «пустой пинг», чтобы сразу открыть соединение
            yield "event: ping\ndata: {}\n\n"
            while True:
                payload = q.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            with _lock:
                try:
                    _listeners.remove(q)
                except ValueError:
                    pass

    return complaints_bp.response_class(event_stream(), mimetype="text/event-stream")
