# -*- coding: utf-8 -*-
"""案件管理（F1）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Case, CaseImage, DamageInstance, Quote, RegionalRate, User
from ..schemas import CaseCreate, CaseUpdate
from ..serializers import case_to_dict, damage_to_dict, image_to_dict
from ..core.numbers import next_number

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _region_name(db: Session, code: str) -> str:
    row = db.query(RegionalRate).filter(
        RegionalRate.region_code == code, RegionalRate.is_current.is_(True)
    ).first()
    return row.region_name if row else "全国参考"


def _quote_brief(quote: Quote | None) -> dict | None:
    if quote is None:
        return None
    return {
        "id": quote.id,
        "quote_no": quote.quote_no,
        "status": quote.status,
        "total_low": quote.total_low,
        "total_mid": quote.total_mid,
        "total_high": quote.total_high,
        "created_at": quote.created_at,
    }


@router.post("")
def create_case(payload: CaseCreate, db: Session = Depends(get_db),
                user: User = Depends(require_roles("adjuster", "admin"))):
    case = Case(
        case_no=next_number(db, Case, Case.case_no, "C"),
        brand=payload.brand,
        series=payload.series,
        vehicle_year=payload.vehicle_year,
        trim=payload.trim,
        region_code=payload.region_code,
        region_name=_region_name(db, payload.region_code),
        status="draft",
        created_by_id=user.id,
        created_by_name=user.full_name or user.username,
    )
    db.add(case)
    db.flush()
    record_audit(db, user, "create_case", "case", case.id, {"case_no": case.case_no})
    db.commit()
    db.refresh(case)
    return case_to_dict(case)


@router.get("")
def list_cases(
    status: str | None = None,
    keyword: str | None = None,
    damage_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=100, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Case)
    if status:
        query = query.filter(Case.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            (Case.case_no.like(like)) | (Case.brand.like(like)) | (Case.series.like(like))
        )
    if damage_type:
        query = query.filter(
            Case.id.in_(select(DamageInstance.case_id).where(DamageInstance.class_name == damage_type))
        )
    if date_from:
        try:
            query = query.filter(Case.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from 格式应为 YYYY-MM-DD")
    if date_to:
        try:
            query = query.filter(Case.created_at < datetime.fromisoformat(date_to) + timedelta(days=1))
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to 格式应为 YYYY-MM-DD")

    cases = query.order_by(Case.id.desc()).limit(limit).all()
    result = []
    for case in cases:
        image_count = db.query(func.count(CaseImage.id)).filter(CaseImage.case_id == case.id).scalar() or 0
        damage_count = db.query(func.count(DamageInstance.id)).filter(
            DamageInstance.case_id == case.id
        ).scalar() or 0
        quote = db.query(Quote).filter(Quote.case_id == case.id).order_by(Quote.id.desc()).first()
        result.append(case_to_dict(case, image_count, damage_count, _quote_brief(quote)))
    return result


@router.get("/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    images = db.query(CaseImage).filter(CaseImage.case_id == case_id).order_by(CaseImage.id).all()
    damages = db.query(DamageInstance).filter(
        DamageInstance.case_id == case_id
    ).order_by(DamageInstance.id).all()
    quote = db.query(Quote).filter(Quote.case_id == case_id).order_by(Quote.id.desc()).first()
    data = case_to_dict(case, len(images), len(damages), _quote_brief(quote))
    data["images"] = [image_to_dict(i) for i in images]
    data["damages"] = [damage_to_dict(d) for d in damages]
    return data


@router.put("/{case_id}")
def update_case(case_id: int, payload: CaseUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_roles("adjuster", "admin"))):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    if case.status in ("quoted", "reported"):
        raise HTTPException(status_code=409, detail="案件已报价或已出报告，不能修改车辆信息")
    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(case, key, value)
    if "region_code" in changes:
        case.region_name = _region_name(db, changes["region_code"])
    record_audit(db, user, "update_case", "case", case.id, changes)
    db.commit()
    db.refresh(case)
    return case_to_dict(case)
