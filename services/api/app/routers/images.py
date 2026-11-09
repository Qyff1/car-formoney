# -*- coding: utf-8 -*-
"""图片上传与查询（F2）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..config import MAX_IMAGES_PER_CASE
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Case, CaseImage, User
from ..serializers import image_to_dict
from ..core.storage import save_case_image

router = APIRouter(prefix="/api/cases", tags=["images"])


@router.post("/{case_id}/images")
def upload_images(case_id: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                  user: User = Depends(require_roles("adjuster", "admin"))):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    if case.status in ("quoted", "reported"):
        raise HTTPException(status_code=409, detail="案件已报价或已出报告，不能继续上传图片")

    existing = db.query(CaseImage).filter(CaseImage.case_id == case_id).count()
    if existing + len(files) > MAX_IMAGES_PER_CASE:
        raise HTTPException(
            status_code=422,
            detail=f"单个案件最多 {MAX_IMAGES_PER_CASE} 张图片，当前已有 {existing} 张，本次上传 {len(files)} 张",
        )

    saved = []
    for upload in files:
        info = save_case_image(case_id, upload)
        image = CaseImage(case_id=case_id, **info)
        db.add(image)
        db.flush()
        saved.append(image)
    record_audit(db, user, "upload_images", "case", case_id,
                 {"count": len(saved), "image_ids": [i.id for i in saved]})
    db.commit()
    return [image_to_dict(i) for i in saved]


@router.get("/{case_id}/images")
def list_images(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(CaseImage).filter(CaseImage.case_id == case_id).order_by(CaseImage.id).all()
    return [image_to_dict(i) for i in rows]
