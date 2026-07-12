from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import OUTPUT_DIR


DATABASE_PATH = OUTPUT_DIR / "learning_system.db"

DATABASE_URL = (
    f"sqlite:///{DATABASE_PATH.resolve().as_posix()}"
)


class Base(DeclarativeBase):
    """所有 SQLAlchemy Model 的基底類別。"""


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection,
    connection_record,
) -> None:
    """啟用 SQLite Foreign Key 約束。"""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_database_session() -> Session:
    """建立新的資料庫操作 Session。"""

    return SessionLocal()


def ensure_database_directory() -> Path:
    """確認 outputs 資料夾存在。"""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return DATABASE_PATH