# -*- coding: utf-8 -*-
"""模型版本管理（F8）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import ModelVersion, User

router = APIRouter(prefix="/api/model-versions", tags=["model-versions"])


class ModelVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weights_path: str = Field(min_length=1, max_length=500)
    metrics: dict | None = None
    train_config: dict | None = None
    dataset_hash: str | None = Field(default=None, max_length=64)


def _dump(row: ModelVersion) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "weights_path": row.weights_path,
        "metrics": row.metrics,
        "train_config": row.train_config,
        "dataset_hash": row.dataset_hash,
        "is_active": row.is_active,
        "created_at": row.created_at,
    }


@router.get("")
def list_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_dump(r) for r in db.query(ModelVersion).order_by(ModelVersion.id).all()]


@router.post("")
def register_model(payload: ModelVersionCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    if db.query(ModelVersion).filter(ModelVersion.name == payload.name).first():
        raise HTTPException(status_code=409, detail="模型版本名称已存在")
    row = ModelVersion(name=payload.name, weights_path=payload.weights_path,
                       metrics=payload.metrics, train_config=payload.train_config,
                       dataset_hash=payload.dataset_hash)
    db.add(row)
    db.flush()
    record_audit(db, user, "register_model", "model_version", row.id, payload.model_dump())
    db.commit()
    db.refresh(row)
    return _dump(row)


@router.post("/{model_id}/activate")
def activate_model(model_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin"))):
    row = db.get(ModelVersion, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模型版本不存在")
    db.query(ModelVersion).update({ModelVersion.is_active: False})
    row.is_active = True
    record_audit(db, user, "activate_model", "model_version", row.id, {"name": row.name})
    db.commit()
    db.refresh(row)
    return _dump(row)
