from __future__ import annotations

from src.database.database import (
    Base,
    DATABASE_PATH,
    engine,
    ensure_database_directory,
)
from src.database import models  # noqa: F401


def initialize_database() -> None:
    """建立 SQLite 資料庫與所有資料表。"""

    ensure_database_directory()

    Base.metadata.create_all(
        bind=engine,
    )

    print("SQLite 學習資料庫初始化完成。")
    print(f"資料庫位置：{DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()