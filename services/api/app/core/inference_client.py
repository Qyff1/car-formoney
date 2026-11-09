# -*- coding: utf-8 -*-
"""调用推理引擎并在案件表上落结果。"""
from __future__ import annotations

from pathlib import Path

from ..config import INFER_CONF, INFER_DEVICE, INFER_IMGSZ, INFER_IOU, OVERLAY_DIR, REVIEW_CONFIDENCE, UPLOAD_DIR


def analyze_image(image_path: str, overlay_rel: str, weights: str) -> list[dict]:
    from services.inference.engine import get_segmenter

    overlay_abs = UPLOAD_DIR / overlay_rel
    segmenter = get_segmenter(weights, INFER_IMGSZ, INFER_CONF, INFER_IOU, INFER_DEVICE)
    instances = segmenter.predict(image_path, str(overlay_abs))
    for item in instances:
        item["needs_review"] = item["confidence"] < REVIEW_CONFIDENCE
    return instances


def new_overlay_rel(image_id: int) -> str:
    path = OVERLAY_DIR / f"image_{image_id}.jpg"
    return path.relative_to(UPLOAD_DIR).as_posix()


def absolute(rel_path: str) -> str:
    return str(UPLOAD_DIR / Path(rel_path))
