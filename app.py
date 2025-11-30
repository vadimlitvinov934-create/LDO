from datetime import timedelta
from flask import Flask, redirect, session

from config import Config
from core.db_init import init_database

# Импортируем Blueprint-ы
from core.auth_bp import auth_bp
from core.checkin_bp import checkin_bp
from core.journal_bp import journal_bp
from core.student_bp import student_bp
from core.api_bp import api_bp
from core.complaints_bp import complaints_bp
from core.head_bp import head_bp
from core.curator_bp import curator_bp
from core.starosta import starosta_bp
from core.tech_bp import tech_bp
from core.chat_bp import chat_bp  # <--- [1] Импортируем ЧАТ

# ───────────────── helpers для шаблонов ─────────────────

def status_label(value: str) -> str:
    """
    Человекочитаемая подпись статуса посещаемости.
    """
    if not value:
        return ""
    v = value.lower()
    mapping = {
        "present": "Присутствовал",
        "late": "Опоздал",
        "absent": "Отсутствовал",
        "excused": "Уважительная",
    }
    return mapping.get(v, value)


# ───────────────── создание приложения ─────────────────

app = Flask(__name__)
app.config.from_object(Config)

# если в Config не задан секрет — подстрахуемся
if not app.secret_key:
    app.secret_key = "change-me-ldo-secret-key"

app.permanent_session_lifetime = timedelta(days=30)

# Инициализация базы
init_database()

# Регистрация блюпринтов
app.register_blueprint(auth_bp)
app.register_blueprint(checkin_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(student_bp)
app.register_blueprint(api_bp)
app.register_blueprint(complaints_bp)
app.register_blueprint(head_bp)
app.register_blueprint(curator_bp)
app.register_blueprint(starosta_bp)
app.register_blueprint(tech_bp)
app.register_blueprint(chat_bp)  # <--- [2] Регистрируем ЧАТ

# Регистрация Jinja-фильтров
app.jinja_env.filters["status_label"] = status_label


# ───────────────── маршруты ─────────────────

@app.route("/")
def index():
    """
    Главная: редирект в зависимости от роли.
    """
    role = (session.get("user") or {}).get("role")

    if role == "tech":
        return redirect("/tech")
    if role == "head":
        return redirect("/head")
    if role == "starosta":
        return redirect("/starosta")
    if role == "student":
        return redirect("/student")
    if role == "curator":
        return redirect("/curator")

    # нет роли → на страницу логина
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)