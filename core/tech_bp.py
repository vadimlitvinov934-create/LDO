# core/tech_bp.py

from flask import Blueprint, render_template
from core.auth_bp import require_role
from models import SessionLocal, User, Student
from sqlalchemy import func

tech_bp = Blueprint("tech_bp", __name__)

@tech_bp.route("/tech")
@require_role("tech")
def tech_dashboard():
    """Панель управления техподдержки."""
    
    session_db = SessionLocal()
    try:
        # Загрузим список сотрудников и кол-во студентов для статистики
        users = session_db.query(User).all() 
        student_count = session_db.query(Student).count()
    finally:
        session_db.close()

    return render_template("tech_dashboard.html", users=users, student_count=student_count)