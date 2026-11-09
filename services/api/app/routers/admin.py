# -*- coding: utf-8 -*-
"""管理员：账号列表与审计日志。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import AuditLog, User
from ..serializers import user_to_dict

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    return [user_to_dict(u) for u in db.query(User).order_by(User.id).all()]


@router.get("/audit-logs")
def list_audit_logs(limit: int = 100, db: Session = Depends(get_db),
                    _: User = Depends(require_roles("admin"))):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "role": r.role,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]
