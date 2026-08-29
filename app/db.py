from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_schema():
    """轻量迁移：旧库缺列时补齐（SQLite 支持 ADD COLUMN）。"""
    import uuid

    needed = {
        "chat_messages": {"session_id": "VARCHAR(36) DEFAULT ''"},
        "classes": {c: "TEXT DEFAULT ''" for c in (
            "teacher_segments", "staff_no", "gender", "room_no", "room_type",
            "room_weeks", "room_periods", "building", "floor",
            "course_category", "course_attribution")},
    }
    with engine.connect() as conn:
        for table, cols in needed.items():
            try:
                existing = {r[1] for r in conn.exec_driver_sql(
                    f"PRAGMA table_info({table})").fetchall()}
            except Exception:
                continue
            if not existing:
                continue
            for col, ddl in cols.items():
                if col not in existing:
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
                        conn.commit()
                    except Exception:
                        pass
        # 旧聊天消息归入一个遗留会话
        try:
            chat_cols = {r[1] for r in conn.exec_driver_sql(
                "PRAGMA table_info(chat_messages)").fetchall()}
            if "session_id" in chat_cols:
                empty = conn.exec_driver_sql(
                    "SELECT count(*) FROM chat_messages WHERE session_id=''").fetchone()[0]
                if empty:
                    legacy = uuid.uuid4().hex
                    conn.exec_driver_sql(
                        f"UPDATE chat_messages SET session_id='{legacy}' WHERE session_id=''")
                    conn.commit()
        except Exception:
            pass


_migrate_schema()
