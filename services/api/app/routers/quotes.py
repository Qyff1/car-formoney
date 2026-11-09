# -*- coding: utf-8 -*-
"""报价（F5）。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Case, DamageInstance, Quote, User
from ..schemas import QuoteConfirmRequest, QuoteRequest
from ..core.numbers import next_number
from ..core.pricing_engine import PricingError, build_quote, quote_to_dict

router = APIRouter(prefix="/api", tags=["quotes"])


@router.post("/quotes")
def create_quote(payload: QuoteRequest, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("adjuster", "admin"))):
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    damages = db.query(DamageInstance).filter(
        DamageInstance.case_id == case.id
    ).order_by(DamageInstance.id).all()
    try:
        quote = build_quote(db, case, damages, user.full_name or user.username)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    quote.quote_no = next_number(db, Quote, Quote.quote_no, "Q")
    quote.manual_override_reason = payload.manual_override_reason
    db.add(quote)
    db.flush()
    record_audit(db, user, "create_quote", "quote", quote.id,
                 {"case_id": case.id, "total_mid": quote.total_mid})
    db.commit()
    db.refresh(quote)
    return quote_to_dict(quote)


@router.post("/quotes/preview")
def preview_quote(payload: QuoteRequest, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("adjuster", "admin"))):
    """按当前已确认损伤试算报价，不落库，供工作台实时查看金额变化。"""
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    damages = db.query(DamageInstance).filter(
        DamageInstance.case_id == case.id
    ).order_by(DamageInstance.id).all()
    priced = [d for d in damages if d.confirmed and d.part_code]
    pending = len(damages) - len(priced)
    if not priced:
        return {
            "case_id": case.id,
            "ready": False,
            "pending_count": pending,
            "total_low": 0.0,
            "total_mid": 0.0,
            "total_high": 0.0,
            "items": [],
            "hit_rules": [],
        }
    try:
        quote = build_quote(db, case, priced, user.full_name or user.username)
    except PricingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    data = quote_to_dict(quote)
    data["ready"] = pending == 0
    data["pending_count"] = pending
    return data


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="报价不存在")
    return quote_to_dict(quote)


@router.get("/cases/{case_id}/quotes")
def list_case_quotes(case_id: int, db: Session = Depends(get_db),
                     _: User = Depends(get_current_user)):
    rows = db.query(Quote).filter(Quote.case_id == case_id).order_by(Quote.id.desc()).all()
    return [quote_to_dict(q) for q in rows]


@router.post("/quotes/{quote_id}/confirm")
def confirm_quote(quote_id: int, payload: QuoteConfirmRequest, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("reviewer", "admin"))):
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="报价不存在")
    if quote.status == "confirmed":
        raise HTTPException(status_code=409, detail="报价已确认，不能重复确认")
    quote.status = "confirmed"
    quote.confirmed_by = user.full_name or user.username
    quote.confirmed_at = datetime.now()
    if payload.manual_override_reason:
        quote.manual_override_reason = payload.manual_override_reason
    case = db.get(Case, quote.case_id)
    if case is not None:
        case.status = "quoted"
    record_audit(db, user, "confirm_quote", "quote", quote.id,
                 {"case_id": quote.case_id, "total_mid": quote.total_mid})
    db.commit()
    db.refresh(quote)
    return quote_to_dict(quote)
