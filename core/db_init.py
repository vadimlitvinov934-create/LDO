# core/db_init.py
from models import init_db, SessionLocal

def init_database():
    """Создать таблицы и добавить недостающие колонки в attendance."""
    init_db()
    with SessionLocal() as s:
        conn = s.bind.raw_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(attendance)")
        cols = {row[1] for row in cur.fetchall()}
        alters = []
        if "status" not in cols:
            alters.append("ALTER TABLE attendance ADD COLUMN status TEXT")
        if "reason" not in cols:
            alters.append("ALTER TABLE attendance ADD COLUMN reason TEXT")
        for q in alters:
            cur.execute(q)
        if alters:
            conn.commit()
        cur.close()
        conn.close()
