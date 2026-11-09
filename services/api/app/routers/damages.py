# -*- coding: utf-8 -*-
"""人工确认工作台（F4）。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Case, DamageInstance, PartCatalog, User
from ..schemas import DamageUpdate
from ..serializers import damage_to_dict
from ..core.pricing_engine import ACTION_LABELS, suggest_damage

router = APIRouter(prefix="/api", tags=["damages"])


@router.get("/cases/{case_id}/damages")
def list_damages(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(DamageInstance).filter(
        DamageInstance.case_id == case_id
    ).order_by(DamageInstance.id).all()
    result = []
    for row in rows:
        data = damage_to_dict(row)
        data["suggestion"] = suggest_damage(db, row)
        result.append(data)
    return result


@router.put("/damages/{damage_id}")
def update_damage(damage_id: int, payload: DamageUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("adjuster", "admin"))):
    damage = db.get(DamageInstance, damage_id)
    if damage is None:
        raise HTTPException(status_code=404, detail="损伤实例不存在")
    case = db.get(Case, damage.case_id)
    if case is not None and case.status in ("quoted", "reported"):
        raise HTTPException(status_code=409, detail="案件已报价或已出报告，不能再修改损伤确认信息")

    changes = payload.model_dump(exclude_none=True)
    if "part_code" in changes:
        part = db.query(PartCatalog).filter(
            PartCatalog.part_code == changes["part_code"], PartCatalog.is_current.is_(True)
        ).first()
        if part is None:
            raise HTTPException(status_code=400, detail=f"部件 {changes['part_code']} 不存在")
        damage.part_name = changes.pop("part_name", None) or part.part_name
    if "action" in changes and "method" not in changes:
        damage.method = ACTION_LABELS.get(changes["action"], changes["action"])
    for key, value in changes.items():
        setattr(damage, key, value)

    if payload.confirmed:
        missing = [name for name, value in {
            "受损部件": damage.part_code,
            "严重度": damage.severity_band,
            "维修动作": damage.action,
        }.items() if not value]
        if missing:
            raise HTTPException(status_code=422, detail=f"确认前请先填写：{'、'.join(missing)}")
        damage.confirmed = True
        damage.confirmed_by = user.full_name or user.username
        damage.confirmed_at = datetime.now()
    elif payload.confirmed is False:
        damage.confirmed = False
        damage.confirmed_by = None
        damage.confirmed_at = None

    record_audit(db, user, "update_damage", "damage", damage.id, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(damage)
    data = damage_to_dict(damage)
    data["suggestion"] = suggest_damage(db, damage)
    return data
