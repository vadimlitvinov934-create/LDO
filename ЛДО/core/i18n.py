from flask import session

# Список поддерживаемых языков
LANGUAGES = ["ru", "kz", "en"]

# Словари переводов
TRANSLATIONS = {
    "ru": {
        "site_title": "LDO Посещаемость",
        "nav_home": "Главная",
        "nav_checkin": "Отметка посещаемости",
        "nav_journal": "Журнал",
        "nav_head": "Заведующая",
        "nav_starosta": "Староста",
        "nav_student": "Студент",
        "nav_admin": "Админ",
        "nav_logout": "Выход",

        "login_title": "Вход в систему",
        "login_username": "Логин",
        "login_password": "Пароль",
        "login_button": "Войти",

        "group": "Группа",
        "statistics": "Статистика",
        "attendance_table": "Таблица посещаемости по студентам",
        "daily_journal": "Журнал за день",

        "present": "Присутствовал",
        "late": "Опоздал",
        "absent": "Отсутствовал",
        "excused": "Уважительная",
    },
    "kz": {
        "site_title": "LDO Қатысу жүйесі",
        "nav_home": "Басты бет",
        "nav_checkin": "Қатысуды белгілеу",
        "nav_journal": "Журнал",
        "nav_head": "Бөлім меңгерушісі",
        "nav_starosta": "Староста",
        "nav_student": "Студент",
        "nav_admin": "Админ",
        "nav_logout": "Шығу",

        "login_title": "Жүйеге кіру",
        "login_username": "Логин",
        "login_password": "Құпия сөз",
        "login_button": "Кіру",

        "group": "Топ",
        "statistics": "Статистика",
        "attendance_table": "Студенттердің қатысу кестесі",
        "daily_journal": "Күндік журнал",

        "present": "Қатысты",
        "late": "Кешікті",
        "absent": "Қатыспады",
        "excused": "Себепті",
    },
    "en": {
        "site_title": "LDO Attendance",
        "nav_home": "Home",
        "nav_checkin": "Check-in",
        "nav_journal": "Journal",
        "nav_head": "Head",
        "nav_starosta": "Starosta",
        "nav_student": "Student",
        "nav_admin": "Admin",
        "nav_logout": "Logout",

        "login_title": "Sign in",
        "login_username": "Username",
        "login_password": "Password",
        "login_button": "Sign in",

        "group": "Group",
        "statistics": "Statistics",
        "attendance_table": "Attendance table",
        "daily_journal": "Daily journal",

        "present": "Present",
        "late": "Late",
        "absent": "Absent",
        "excused": "Excused",
    },
}


def get_lang() -> str:
    """Текущий язык из сессии (по умолчанию ru)."""
    lang = session.get("lang", "ru")
    if lang not in LANGUAGES:
        lang = "ru"
    return lang


def _(key: str) -> str:
    """Функция перевода: _(key). Если нет ключа — вернёт сам key."""
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)
