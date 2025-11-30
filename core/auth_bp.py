# core/auth_bp.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from werkzeug.security import check_password_hash
from models import SessionLocal, User, Student

auth_bp = Blueprint("auth_bp", __name__)

def require_role(*roles):
    """Декоратор проверки доступа."""
    def _wrap(view):
        @wraps(view)
        def _inner(*a, **kw):
            user = session.get("user")
            # Если роли нет в списке разрешенных
            if not user or user.get("role") not in roles:
                flash("Доступ запрещен или требуется вход.", "error")
                return redirect(url_for("auth_bp.login"))
            return view(*a, **kw)
        return _inner
    return _wrap

@auth_bp.route("/")
def root():
    return redirect(url_for("auth_bp.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        fio = (request.form.get("fio") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not fio or not password:
            flash("Введите ФИО и пароль", "error")
            return render_template("login.html")

        session_db = SessionLocal()
        try:
            # 1. Сначала ищем сотрудника (User)
            # Мы ищем по полю fio, так как в логин форме вводится fio
            user = session_db.query(User).filter(User.fio == fio).first()
            
            if user and check_password_hash(user.password_hash, password):
                # Успешный вход сотрудника
                home_url = "/journal" # default
                if user.role == "head": home_url = "/head"
                if user.role == "starosta": home_url = "/starosta"
                if user.role == "admin": home_url = "/admin/console"

                session["user"] = {"role": user.role, "fio": user.fio}
                session.permanent = True
                return redirect(home_url)

            # 2. Если сотрудник не найден, ищем студента (Student)
            student = session_db.query(Student).filter(Student.full_name == fio).first()
            
            if student and student.password_hash and check_password_hash(student.password_hash, password):
                # Успешный вход студента
                session["user"] = {"role": "student", "fio": student.full_name}
                session.permanent = True
                return redirect("/student")

            flash("Неверные ФИО или пароль", "error")
        
        finally:
            session_db.close()

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth_bp.login"))