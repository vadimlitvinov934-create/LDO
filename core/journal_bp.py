from flask import Blueprint, render_template, jsonify, request, session
from models import SessionLocal, Student, Attendance, PeriodSkip
from datetime import date, datetime, timedelta
from config import get_schedule_for, today_key, now_minutes
from core.helpers import (
    parse_date_param,
    compute_status_by_mark,
    compute_status,
    STATUS_LABELS,
    REASON_LABELS,
)
from core.auth_bp import require_role
from core.permissions import get_curator_groups
from sqlalchemy import func

journal_bp = Blueprint("journal_bp", __name__)

VALID_STATUSES = {"present", "late", "absent", "excused"}


@journal_bp.route("/journal")
@require_role("curator")
def journal():
    d = parse_date_param(request.args.get("d"))
    today_d = date.today()

    # выбранная группа для фильтра (может быть пустой = все группы куратора)
    selected_group = (request.args.get("g") or "").strip()

    schedule = get_schedule_for(d)
    with SessionLocal() as s:
        # список групп, которые привязаны к этому куратору
        fio = (session.get("user") or {}).get("fio", "")
        curator_groups = [g.strip() for g in (get_curator_groups(fio) or []) if g and g.strip()]

        # базовый запрос по студентам
        q_st = s.query(Student)

        if curator_groups:
            q_st = q_st.filter(func.trim(Student.group_code).in_(curator_groups))
        else:
            # у куратора не настроены группы → искусственно пустой результат
            q_st = q_st.filter(Student.id == -1)

        # если выбрана конкретная группа, сузим дополнительно
        if selected_group:
            q_st = q_st.filter(func.trim(Student.group_code) == selected_group)

        students = q_st.order_by(Student.full_name).all()

        # список групп для выпадающего фильтра
        groups_available = [
            g for (g,) in (
                s.query(func.trim(Student.group_code))
                .filter(func.trim(Student.group_code).in_(curator_groups))
                .distinct()
                .order_by(func.trim(Student.group_code))
            )
        ]

        # все отметки за день (по всем группам куратора)
        recs = s.query(Attendance).filter(Attendance.date == d).all()

        # все skip'ы по дате для групп этого куратора
        q_sk = s.query(PeriodSkip).filter(PeriodSkip.date == d)
        if curator_groups:
            q_sk = q_sk.filter(func.trim(PeriodSkip.group_code).in_(curator_groups))
        skips = q_sk.all()

    # построим карту: group_code -> set(period_code)
    skips_by_group = {}
    for r in skips:
        g_code = (r.group_code or "").strip()
        if not g_code:
            continue
        skips_by_group.setdefault(g_code, set()).add(r.period_code)

    # для шапки: если выбрана группа, её skip'ы
    if selected_group:
        skipped_codes = skips_by_group.get(selected_group, set())
    else:
        skipped_codes = set()

    # карта записей посещаемости
    rec_map = {(r.student_id, r.period_code): r for r in recs}

    is_today = (d == today_d)
    nowm = now_minutes()

    table = []
    valid_statuses = {"present", "late", "absent", "excused"}
    day_counts = {"present": 0, "late": 0, "absent": 0, "excused_sick": 0, "excused_other": 0}
    per_student_stats = {}

    # сколько пар в принципе может быть за день (используем для заголовков/подсказок)
    if selected_group:
        group_skips_for_pairs = skips_by_group.get(selected_group, set())
        pairs_considered = sum(
            1 for p in schedule
            if p["code"].startswith("p") and p["code"] not in group_skips_for_pairs
        )
    else:
        # если смотрим все группы сразу — считаем по чистому расписанию
        pairs_considered = sum(1 for p in schedule if p["code"].startswith("p"))

    for i, st in enumerate(students, start=1):
        row = {
            "num": i,
            "id": st.id,
            "uid": st.uid,
            "full_name": st.full_name,
            "cells": [],
        }

        # какие пары отменены именно у ЭТОЙ группы
        st_group = (st.group_code or "").strip()
        group_skipped_codes = skips_by_group.get(st_group, set())

        attended = 0
        total = 0

        for p in schedule:
            code = p["code"]
            rec = rec_map.get((st.id, code))

            if rec:
                stored_status = (rec.status or "").strip()
                reason = (rec.reason or None)
                mark = rec.time.strftime("%H:%M") if rec.time else None
                status = stored_status or (
                    compute_status(mark, p, nowm) if is_today else compute_status_by_mark(mark, p)
                )
            else:
                reason = None
                mark = None
                status = compute_status(mark, p, nowm) if is_today else ""

            is_skipped = False
            # Если для группы студента эта пара отменена → принудительно skip
            if code in group_skipped_codes and code.startswith("p"):
                status = "skip"
                mark = None
                reason = None
                is_skipped = True

            row["cells"].append(
                {
                    "code": code,
                    "status": status,
                    "reason": reason,
                    "mark": mark,
                    "is_skipped": is_skipped,
                }
            )

            if status in valid_statuses:
                total += 1
                if status in {"present", "late"}:
                    attended += 1
                if status == "present":
                    day_counts["present"] += 1
                elif status == "late":
                    day_counts["late"] += 1
                elif status == "absent":
                    day_counts["absent"] += 1
                elif status == "excused":
                    rtxt = (reason or "").strip().lower()
                    if rtxt in {"sick", "болел", "болеет", "ill", "illness"}:
                        day_counts["excused_sick"] += 1
                    else:
                        day_counts["excused_other"] += 1

        table.append(row)
        per_student_stats[st.id] = {
            "name": st.full_name,
            "uid": st.uid,
            "attended": attended,
            "total": total,
        }

    day_total_considered = sum(day_counts.values())
    pct = lambda x: round((x / day_total_considered) * 100, 1) if day_total_considered else 0.0

    # объединяем присутствие + опоздание
    present_all = day_counts["present"] + day_counts["late"]

    day_percentages = {
        "present": pct(day_counts["present"]),
        "late": pct(day_counts["late"]),
        "present_all": pct(present_all),   # основной показатель
        "absent": pct(day_counts["absent"]),
        "excused_sick": pct(day_counts["excused_sick"]),
        "excused_other": pct(day_counts["excused_other"]),
        "total": day_total_considered,
    }

    ranking = []
    for st_id, stv in per_student_stats.items():
        total = stv["total"]
        attended = stv["attended"]  # late засчитывается
        percent = round((attended / total) * 100, 1) if total else 0.0
        ranking.append(
            {
                "name": stv["name"],
                "uid": stv["uid"],
                "attended": attended,
                "total": total,
                "percent": percent,
            }
        )
    ranking.sort(key=lambda r: (-r["percent"], -r["attended"], r["name"]))

    nav_prev = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    nav_next = min(today_d, d + timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "journal.html",
        schedule=schedule,
        table=table,
        today=today_key(),
        selected_date=d.strftime("%Y-%m-%d"),
        status_labels=STATUS_LABELS,
        reason_labels=REASON_LABELS,
        skipped_codes=skipped_codes,     # для заголовка (если выбрана группа)
        day_counts=day_counts,
        day_percentages=day_percentages,
        ranking=ranking,
        has_data=(day_total_considered > 0),
        total_students=len(students),
        pairs_considered=pairs_considered,
        nav_prev=nav_prev,
        nav_next=nav_next,
        # фильтр групп
        groups_available=groups_available,
        selected_group=selected_group,
    )


@journal_bp.route("/journal/skip", methods=["POST"])
@require_role("curator")
def journal_skip_toggle():
    d = parse_date_param(request.form.get("d"))
    code = (request.form.get("code") or "").strip()
    on = request.form.get("on") == "1"
    g = (request.form.get("g") or "").strip()

    if not code or not code.startswith("p"):
        return jsonify({"ok": False, "error": "Неверный period_code"}), 400

    fio = (session.get("user") or {}).get("fio", "")
    curator_groups = [gg.strip() for gg in (get_curator_groups(fio) or []) if gg and gg.strip()]

    if not curator_groups:
        return jsonify({"ok": False, "error": "Нет доступных групп"}), 400

    with SessionLocal() as s:
        if g == "__ALL__":
            # применяем ко всем группам куратора
            for grp in curator_groups:
                ex = (
                    s.query(PeriodSkip)
                    .filter_by(date=d, period_code=code, group_code=grp)
                    .first()
                )
                if on and not ex:
                    s.add(PeriodSkip(date=d, period_code=code, group_code=grp))
                elif not on and ex:
                    s.delete(ex)
            s.commit()
        else:
            if not g:
                return jsonify({"ok": False, "error": "Не выбрана группа"}), 400
            if g not in curator_groups:
                return jsonify({"ok": False, "error": "Нет доступа к группе"}), 403

            ex = (
                s.query(PeriodSkip)
                .filter_by(date=d, period_code=code, group_code=g)
                .first()
            )
            if on and not ex:
                s.add(PeriodSkip(date=d, period_code=code, group_code=g))
                s.commit()
            elif not on and ex:
                s.delete(ex)
                s.commit()

    return jsonify({"ok": True})


@journal_bp.route("/journal/set", methods=["POST"])
@require_role("curator")
def journal_set_status():
    try:
        d = parse_date_param(request.form.get("d"))
    except Exception:
        return jsonify({"ok": False, "error": "bad date"}), 400

    try:
        student_id = int(request.form.get("student_id") or "0")
    except ValueError:
        student_id = 0
    period_code = (request.form.get("period_code") or "").strip()
    status = (request.form.get("status") or "").strip()
    reason = (request.form.get("reason") or "").strip() or None

    if not (student_id and period_code.startswith("p") and status in VALID_STATUSES):
        return jsonify({"ok": False, "error": "bad params"}), 400

    now_t = datetime.now().time()
    with SessionLocal() as s:
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
                student_id=student_id,
                time=now_t,
            )
            s.add(rec)
        rec.status = status
        rec.reason = reason if status == "excused" else None
        if not rec.time:
            rec.time = now_t
        s.commit()
        time_str = rec.time.strftime("%H:%M") if rec.time else ""
        label = STATUS_LABELS.get(status, status)
        reason_label = REASON_LABELS.get(reason) if reason else None

    return jsonify(
        {
            "ok": True,
            "status": status,
            "label": label,
            "time": time_str,
            "reason": reason_label,
        }
    ), 200
