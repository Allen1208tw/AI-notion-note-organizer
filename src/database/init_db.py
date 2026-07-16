from __future__ import annotations

from sqlalchemy import inspect

from src.database.database import (
    Base,
    DATABASE_PATH,
    engine,
    ensure_database_directory,
)
from src.database import models  # noqa: F401


def get_schema_issues() -> list[str]:
    """Return missing tables or columns in an existing SQLite database."""

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    issues: list[str] = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            issues.append(f"缺少資料表：{table_name}")
            continue

        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing_columns = set(table.columns.keys()) - existing_columns

        for column_name in sorted(missing_columns):
            issues.append(f"缺少欄位：{table_name}.{column_name}")

    return issues


def initialize_database() -> list[str]:
    """建立 SQLite 資料庫與所有資料表。"""

    ensure_database_directory()

    Base.metadata.create_all(
        bind=engine,
    )

    issues = get_schema_issues()

    print("SQLite 學習資料庫初始化完成。")
    print(f"資料庫位置：{DATABASE_PATH}")

    if issues:
        print("資料庫 Schema 需要更新：")
        for issue in issues:
            print(f"- {issue}")

    return issues


if __name__ == "__main__":
    initialize_database()
