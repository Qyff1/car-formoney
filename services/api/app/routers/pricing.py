# -*- coding: utf-8 -*-
"""价格与规则主数据（F7）：版本化维护，不覆盖历史。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    LaborStandard,
    MaterialStandard,
    PartCatalog,
    PricingRule,
    RegionalRate,
    SeverityThreshold,
    User,
    VehicleModel,
)
from ..schemas import (
    LaborUpdate,
    MaterialUpdate,
    PartPriceUpdate,
    PricingRuleUpdate,
    RegionalRateUpdate,
)
from ..core.pricing_engine import (
    ACTION_LABELS,
    DAMAGE_LABELS,
    FORMULA_TEXT,
    SEVERITY_LABELS,
)

router = APIRouter(prefix="/api/pricing", tags=["pricing"])

SKIP_COLUMNS = {"id", "is_current", "version", "created_at", "effective_from"}

ROLLBACK_MODELS = {
    "parts": PartCatalog,
    "labor": LaborStandard,
    "materials": MaterialStandard,
    "regions": RegionalRate,
    "rules": PricingRule,
}


def _identity(row, kind: str) -> tuple:
    if kind == "parts":
        # 同一配件按车型与年款分别定价，历史版本必须按三者共同识别
        return (row.vehicle_model_id, row.vehicle_year, row.part_code)
    if kind == "labor":
        return (row.part_code, row.damage_type, row.action, row.severity_band)
    if kind == "materials":
        return (row.part_code, row.action, row.severity_band)
    if kind == "regions":
        return (row.region_code,)
    return (row.rule_code,)


def _dump(row) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _new_version(db: Session, row, changes: dict):
    row.is_current = False
    data = {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in SKIP_COLUMNS
    }
    data.update(changes)
    if hasattr(row, "effective_from"):
        data["effective_from"] = date.today()
    data["version"] = row.version + 1
    data["is_current"] = True
    new_row = type(row)(**data)
    db.add(new_row)
    db.flush()
    return new_row


@router.get("/vehicle-models")
def vehicle_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """可选车型库：排除通用兜底车型，供建案时搜索选择。"""
    rows = (
        db.query(VehicleModel)
        .filter(VehicleModel.is_active.is_(True), VehicleModel.is_default.is_(False))
        .order_by(VehicleModel.brand, VehicleModel.series, VehicleModel.year_from)
        .all()
    )
    return [
        {
            "id": row.id,
            "code": row.code,
            "brand": row.brand,
            "series": row.series,
            "year_from": row.year_from,
            "year_to": row.year_to,
            "trim": row.trim,
        }
        for row in rows
    ]


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {
        "formula": FORMULA_TEXT,
        "labels": {
            "damage_types": DAMAGE_LABELS,
            "actions": ACTION_LABELS,
            "severities": SEVERITY_LABELS,
        },
        "vehicle_models": [_dump(r) for r in db.query(VehicleModel).order_by(VehicleModel.id)],
        "parts": [
            _dump(r)
            for r in db.query(PartCatalog)
            .filter(PartCatalog.is_current.is_(True))
            .order_by(PartCatalog.id)
        ],
        "labor": [
            _dump(r)
            for r in db.query(LaborStandard)
            .filter(LaborStandard.is_current.is_(True))
            .order_by(LaborStandard.id)
        ],
        "materials": [
            _dump(r)
            for r in db.query(MaterialStandard)
            .filter(MaterialStandard.is_current.is_(True))
            .order_by(MaterialStandard.id)
        ],
        "regions": [
            _dump(r)
            for r in db.query(RegionalRate)
            .filter(RegionalRate.is_current.is_(True))
            .order_by(RegionalRate.id)
        ],
        "rules": [
            _dump(r)
            for r in db.query(PricingRule)
            .filter(PricingRule.is_current.is_(True))
            .order_by(PricingRule.damage_type, PricingRule.priority.desc())
        ],
        "thresholds": [
            _dump(r)
            for r in db.query(SeverityThreshold)
            .filter(SeverityThreshold.is_current.is_(True))
            .order_by(SeverityThreshold.id)
        ],
    }


@router.get("/regions")
def regions(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(RegionalRate).filter(RegionalRate.is_current.is_(True)).all()
    return [_dump(r) for r in rows]


@router.put("/parts/{row_id}")
def update_part(row_id: int, payload: PartPriceUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_roles("admin"))):
    row = db.get(PartCatalog, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="配件不存在")
    if not (payload.price_low <= payload.list_price <= payload.price_high):
        raise HTTPException(status_code=422, detail="价格需满足 低 ≤ 中 ≤ 高")
    new_row = _new_version(db, row, payload.model_dump())
    record_audit(db, user, "update_part_price", "part_catalog", new_row.id,
                 {"part_code": row.part_code, "old": _dump(row), "new": _dump(new_row)})
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)


@router.put("/labor/{row_id}")
def update_labor(row_id: int, payload: LaborUpdate, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("admin"))):
    row = db.get(LaborStandard, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="工时标准不存在")
    new_row = _new_version(db, row, payload.model_dump())
    record_audit(db, user, "update_labor", "labor_standard", new_row.id, payload.model_dump())
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)


@router.put("/materials/{row_id}")
def update_material(row_id: int, payload: MaterialUpdate, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin"))):
    row = db.get(MaterialStandard, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="材料标准不存在")
    new_row = _new_version(db, row, payload.model_dump())
    record_audit(db, user, "update_material", "material_standard", new_row.id, payload.model_dump())
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)


@router.put("/regions/{row_id}")
def update_region(row_id: int, payload: RegionalRateUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("admin"))):
    row = db.get(RegionalRate, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="地区费率不存在")
    new_row = _new_version(db, row, payload.model_dump())
    record_audit(db, user, "update_region", "regional_rate", new_row.id, payload.model_dump())
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)


@router.put("/rules/{row_id}")
def update_rule(row_id: int, payload: PricingRuleUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_roles("admin"))):
    row = db.get(PricingRule, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="定价规则不存在")
    changes = payload.model_dump()
    if changes["area_ratio_max"] is not None and changes["area_ratio_max"] <= changes["area_ratio_min"]:
        raise HTTPException(status_code=422, detail="面积上限必须大于面积下限")
    new_row = _new_version(db, row, changes)
    record_audit(db, user, "update_rule", "pricing_rule", new_row.id,
                 {"rule_code": row.rule_code, "changes": changes})
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)


def _require_model(kind: str):
    model = ROLLBACK_MODELS.get(kind)
    if model is None:
        raise HTTPException(status_code=404, detail="不支持的主数据类型")
    return model


@router.get("/{kind}/{row_id}/history")
def list_history(kind: str, row_id: int, db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    model = _require_model(kind)
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="主数据记录不存在")
    identity = _identity(row, kind)
    rows = [
        r for r in db.query(model).all()
        if _identity(r, kind) == identity
    ]
    rows.sort(key=lambda r: r.version, reverse=True)
    return [_dump(r) for r in rows]


@router.post("/{kind}/{row_id}/rollback")
def rollback_record(kind: str, row_id: int, target_id: int = Query(gt=0),
                    db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin"))):
    """把历史版本的值作为新版本重新生效，不删除任何历史记录。"""
    model = _require_model(kind)
    current = db.get(model, row_id)
    target = db.get(model, target_id)
    if current is None or target is None:
        raise HTTPException(status_code=404, detail="主数据记录不存在")
    if _identity(current, kind) != _identity(target, kind):
        raise HTTPException(status_code=422, detail="只能回滚到同一主数据记录的历史版本")
    if target.is_current:
        raise HTTPException(status_code=409, detail="目标版本已是当前版本")

    data = {
        c.name: getattr(target, c.name)
        for c in target.__table__.columns
        if c.name not in SKIP_COLUMNS
    }
    data["version"] = current.version + 1
    data["is_current"] = True
    if hasattr(target, "effective_from"):
        data["effective_from"] = date.today()
    current.is_current = False
    new_row = model(**data)
    db.add(new_row)
    db.flush()
    record_audit(db, user, f"rollback_{kind}", model.__tablename__, new_row.id,
                 {"from_id": row_id, "target_id": target_id,
                  "from_version": current.version, "new_version": new_row.version})
    db.commit()
    db.refresh(new_row)
    return _dump(new_row)
