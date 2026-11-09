# -*- coding: utf-8 -*-
"""损伤分析（F3）：调用模型并保存实例。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..config import DEFAULT_WEIGHTS, UPLOAD_DIR
from ..db import get_db
from ..deps import require_roles
from ..models import Case, CaseImage, DamageInstance, ModelVersion, User
from ..schemas import AnalysisRequest
from ..serializers import damage_to_dict, image_to_dict
from ..core.inference_client import analyze_image
from ..core.pricing_engine import default_part_for_class

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.post("")
def create_analysis(payload: AnalysisRequest, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("adjuster", "admin"))):
    case = db.get(Case, payload.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    if case.status in ("quoted", "reported"):
        raise HTTPException(status_code=409, detail="案件已报价或已出报告，不能重新分析")

    images = db.query(CaseImage).filter(CaseImage.case_id == case.id).order_by(CaseImage.id).all()
    if payload.image_ids:
        images = [i for i in images if i.id in set(payload.image_ids)]
    if not images:
        raise HTTPException(status_code=400, detail="案件没有可分析的图片")

    if payload.model_version:
        model = db.query(ModelVersion).filter(ModelVersion.name == payload.model_version).first()
    else:
        model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    weights = model.weights_path if model else str(DEFAULT_WEIGHTS)
    model_name = model.name if model else "yolov8s-seg-baseline"

    previous_status = case.status
    case.status = "analyzing"
    db.commit()

    created: list[DamageInstance] = []
    try:
        for image in images:
            db.query(DamageInstance).filter(DamageInstance.image_id == image.id).delete()
            overlay_rel = f"overlays/image_{image.id}.jpg"
            instances = analyze_image(str(UPLOAD_DIR / image.path), overlay_rel, weights)
            image.overlay_path = overlay_rel
            image.model_name = model_name
            for item in instances:
                damage = DamageInstance(
                    case_id=case.id,
                    image_id=image.id,
                    class_name=item["class_name"],
                    class_id=item["class_id"],
                    confidence=item["confidence"],
                    bbox=item["bbox"],
                    polygons=item["polygons"],
                    mask_area_ratio=item["mask_area_ratio"],
                    part_code=default_part_for_class(item["class_name"]),
                    needs_review=item["needs_review"],
                )
                db.add(damage)
                created.append(damage)
        case.status = "pending_confirm"
        record_audit(db, user, "run_analysis", "case", case.id,
                     {"model": model_name, "image_ids": [i.id for i in images],
                      "damage_count": len(created)})
        db.commit()
    except Exception as exc:
        db.rollback()
        case = db.get(Case, payload.case_id)
        case.status = previous_status
        db.commit()
        raise HTTPException(status_code=500, detail=f"模型推理失败：{exc}")

    return {
        "case_id": case.id,
        "model_version": model_name,
        "damage_count": len(created),
        "images": [image_to_dict(i) for i in images],
        "damages": [damage_to_dict(d) for d in created],
    }
