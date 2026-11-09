# -*- coding: utf-8 -*-
"""审计日志写入。"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .models import AuditLog, User


def _jsonable(value):
    """把 date/datetime 等非 JSON 类型转成可存储形式。"""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def record_audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str = "",
    entity_id: str | int = "",
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else "",
            role=user.role if user else "",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            detail=_jsonable(detail or {}),
        )
    )
