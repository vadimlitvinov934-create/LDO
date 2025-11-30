# core/routes_admin.py
import csv
from io import TextIOWrapper
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import SessionLocal, Student

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/admin/students/upload", methods=["GET", "POST"])
def students_upload():
    """Импорт студентов из CSV: колонки uid,full_name (в заголовке)."""
    if request.method == "GET":
        with SessionLocal() as s:
            count = s.query(Student).count()
        return render_template("students_upload.html", count=count)

    # POST: загрузка файла
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Файл не выбран", "error")
        return redirect(url_for("admin_bp.students_upload"))

    # Читаем как текст UTF-8
    try:
        wrapper = TextIOWrapper(file.stream, encoding="utf-8")
        reader = csv.DictReader(wrapper)
    except Exception as e:
        flash(f"Ошибка чтения CSV: {e}", "error")
        return redirect(url_for("admin_bp.students_upload"))

    added, skipped = 0, 0
    with SessionLocal() as s:
        for row in reader:
            uid = (row.get("uid") or "").strip()
            full_name = (row.get("full_name") or "").strip()
            if not uid or not full_name:
                skipped += 1
                continue
            exists = s.query(Student).filter(Student.uid == uid).first()
            if exists:
                skipped += 1
                continue
            s.add(Student(uid=uid, full_name=full_name))
            added += 1
        s.commit()
    flash(f"Импорт завершён: добавлено {added}, пропущено {skipped}", "ok")
    return redirect(url_for("admin_bp.students_upload"))

@admin_bp.route("/admin/students/seed_demo", methods=["POST"])
def students_seed_demo():
    """Разовая засе́вка демо-студентов (если хочешь быстро проверить UI)."""
    demo = [
        ("1001", "Иванов Иван Иванович"),
        ("1002", "Петров Пётр Петрович"),
        ("1003", "Сидорова Анна Сергеевна"),
        ("1004", "Ким Даурен Ерланович"),
    ]
    with SessionLocal() as s:
        added = 0
        for uid, name in demo:
            if not s.query(Student).filter(Student.uid == uid).first():
                s.add(Student(uid=uid, full_name=name))
                added += 1
        s.commit()
    flash(f"Демо-добавление: создано {added} записей", "ok")
    return redirect(url_for("admin_bp.students_upload"))
