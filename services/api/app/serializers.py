# -*- coding: utf-8 -*-
"""序列化助手：把 ORM 对象转成前端友好的字典。"""
from __future__ import annotations

from .config import CASE_STATUS, ROLE_LABELS
from .models import Case, CaseImage, DamageInstance
from .core.pricing_engine import ACTION_LABELS, DAMAGE_LABELS, SEVERITY_LABELS


def user_to_dict(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
    }


def image_to_dict(image: CaseImage) -> dict:
    return {
        "id": image.id,
        "case_id": image.case_id,
        "filename": image.filename,
        "original_name": image.original_name,
        "url": f"/files/{image.path}",
        "overlay_url": f"/files/{image.overlay_path}" if image.overlay_path else None,
        "width": image.width,
        "height": image.height,
        "model_name": image.model_name,
        "created_at": image.created_at,
    }


def damage_to_dict(damage: DamageInstance) -> dict:
    return {
        "id": damage.id,
        "case_id": damage.case_id,
        "image_id": damage.image_id,
        "class_name": damage.class_name,
        "class_label": DAMAGE_LABELS.get(damage.class_name, damage.class_name),
        "class_id": damage.class_id,
        "confidence": round(damage.confidence, 4),
        "bbox": damage.bbox,
        "polygons": damage.polygons,
        "mask_area_ratio": round(damage.mask_area_ratio, 6),
        "needs_review": damage.needs_review,
        "part_code": damage.part_code,
        "part_name": damage.part_name,
        "severity_band": damage.severity_band,
        "severity_label": SEVERITY_LABELS.get(damage.severity_band or "", ""),
        "action": damage.action,
        "action_label": ACTION_LABELS.get(damage.action or "", ""),
        "method": damage.method,
        "note": damage.note,
        "confirmed": damage.confirmed,
        "confirmed_by": damage.confirmed_by,
        "confirmed_at": damage.confirmed_at,
        "updated_at": damage.updated_at,
    }


def case_to_dict(case: Case, image_count: int = 0, damage_count: int = 0,
                 latest_quote: dict | None = None) -> dict:
    return {
        "id": case.id,
        "case_no": case.case_no,
        "brand": case.brand,
        "series": case.series,
        "vehicle_year": case.vehicle_year,
        "trim": case.trim,
        "region_code": case.region_code,
        "region_name": case.region_name,
        "status": case.status,
        "status_label": CASE_STATUS.get(case.status, case.status),
        "created_by_name": case.created_by_name,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "image_count": image_count,
        "damage_count": damage_count,
        "latest_quote": latest_quote,
    }
