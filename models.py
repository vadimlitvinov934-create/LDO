import os
from typing import Optional
from datetime import date, time as dtime, datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Time, DateTime, Text, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    sessionmaker, scoped_session
)

# ──────────────────────────────────────────────────────────────────────────────
# Конфиг БД
# ──────────────────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL", "sqlite:///ldo.db")


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────────────────────
# СТУДЕНТЫ
# ──────────────────────────────────────────────────────────────────────────────
class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    # Код группы (например: "K-21", "IS-302")
    group_code: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    
    # НОВОЕ ПОЛЕ: Хеш пароля (для входа в личный кабинет)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Все отметки студента
    records: Mapped[list["Attendance"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )


# ──────────────────────────────────────────────────────────────────────────────
# ЖУРНАЛ ПОСЕЩАЕМОСТИ
# ──────────────────────────────────────────────────────────────────────────────
class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    period_code: Mapped[str] = mapped_column(String(8), index=True)
    time: Mapped[Optional[dtime]] = mapped_column(Time, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), index=True)
    student: Mapped["Student"] = relationship(back_populates="records")

    __table_args__ = (
        UniqueConstraint(
            "date",
            "period_code",
            "student_id",
            name="uq_attendance_date_period_student"
        ),
        Index("ix_attendance_student_date", "student_id", "date"),
        Index("ix_attendance_status", "status"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ОТМЕНА УЧЁТА ОТДЕЛЬНЫХ ПАР (НЕ УЧИТЫВАТЬ ПАРУ)
# ──────────────────────────────────────────────────────────────────────────────
class PeriodSkip(Base):
    __tablename__ = "period_skips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    period_code: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    # ВАЖНО: теперь указываем группу, для которой пара отменена
    group_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    __table_args__ = (
        # Главный момент: уникальность по ТРЁМ полям,
        # чтобы одну и ту же пару можно было отменить у разных групп
        UniqueConstraint(
            "date",
            "period_code",
            "group_code",
            name="uq_period_skip_date_code_group",
        ),
        Index("ix_period_skip_group_date", "group_code", "date"),
    )

    def __repr__(self) -> str:
        return f"<PeriodSkip {self.date} {self.period_code} {self.group_code}>"


# ──────────────────────────────────────────────────────────────────────────────
# 💬 ЖАЛОБЫ (от старосты куратору)
# ──────────────────────────────────────────────────────────────────────────────
class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Кто отправил (роль и имя)
    from_role: Mapped[str] = mapped_column(String(20), nullable=False)
    from_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # На кого жалоба и на какую пару
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Причина жалобы
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус жалобы (new/seen/resolved)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)

    def __repr__(self):
        return f"<Complaint id={self.id} on={self.target_name} pair={self.period_index}>"


# ──────────────────────────────────────────────────────────────────────────────
# 🔒 Блокировка отправки старостой (один раз на пару для группы)
# ──────────────────────────────────────────────────────────────────────────────
class StarostaLock(Base):
    __tablename__ = "starosta_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    period_code: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    group_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(255), nullable=False)  # ФИО старосты
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("date", "period_code", "group_code", name="uq_starosta_lock"),
        Index("ix_starosta_lock_group_date", "group_code", "date"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ПОЛЬЗОВАТЕЛИ
# ──────────────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="curator"
    )
    fio: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_role", "role"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ/СЕССИИ
# ──────────────────────────────────────────────────────────────────────────────
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)


def init_db() -> None:
    """
    Создаёт схемы и необходимые индексы.

    ВАЖНО: перед create_all мы дропаем таблицу period_skips,
    чтобы обновилось уникальное ограничение (date, period_code, group_code).
    """
    if DB_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            conn.commit()

    # 🔄 пересоздаём период-скипы (старое ограничение могло быть только по date+period_code)
    from sqlalchemy import inspect

    insp = inspect(engine)
    if "period_skips" in insp.get_table_names():
        PeriodSkip.__table__.drop(engine, checkfirst=True)

    # создаём все таблицы (если нет)
    Base.metadata.create_all(engine)

    # индексы для attendance (как было)
    if DB_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_date_period_student "
                "ON attendance(date, period_code, student_id);"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_attendance_student_date "
                "ON attendance(student_id, date);"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_attendance_status_dup "
                "ON attendance(status);"
            )
            conn.commit()