# -*- coding: utf-8 -*-
"""业务编号生成。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session


def next_number(db: Session, model, column, prefix: str) -> str:
    head = f"{prefix}{datetime.now().strftime('%Y%m%d')}"
    count = db.query(model).filter(column.like(f"{head}%")).count()
    return f"{head}{count + 1:04d}"
