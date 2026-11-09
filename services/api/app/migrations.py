# -*- coding: utf-8 -*-
"""SQLite 轻量迁移：为既有数据库补齐新增列。

不使用第三方迁移框架，仅按 PRAGMA 检查列是否存在后 ALTER TABLE ADD COLUMN，
保证已有 data/app.db 升级后无需重建。新库由 Base.metadata.create_all 直接建全。
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from .db import engine

# 表名 -> [(列名, 列定义)]
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "case_image": [("model_name", "VARCHAR(80)")],
    "model_version": [
        ("train_config", "JSON"),
        ("dataset_hash", "VARCHAR(64)"),
    ],
    "part_catalog": [("vehicle_year", "INTEGER")],
}


def run_migrations(bind=engine) -> None:
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table, columns in COLUMNS.items():
            if table not in tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "users" in tables:
            # 角色收敛：原“定损员”并入“查勘定损员”
            conn.execute(text("UPDATE users SET role = 'adjuster' WHERE role = 'assessor'"))
