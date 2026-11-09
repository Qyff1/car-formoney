# -*- coding: utf-8 -*-
"""图片落盘与校验。"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from ..config import ALLOWED_IMAGE_SUFFIXES, CASE_FILE_DIR, MAX_UPLOAD_MB, UPLOAD_DIR


def save_case_image(case_id: int, upload: UploadFile) -> dict:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支持的图片格式：{suffix or '未知'}")

    raw = upload.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"图片超过 {MAX_UPLOAD_MB} MB 限制")

    try:
        image = Image.open(__import__("io").BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="图片无法解析，请更换文件")

    target_dir = CASE_FILE_DIR / str(case_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix if suffix != '.jpeg' else '.jpg'}"
    target = target_dir / filename
    save_format = "PNG" if filename.lower().endswith(".png") else "JPEG"
    image.save(target, format=save_format, quality=92)

    return {
        "filename": filename,
        "original_name": upload.filename or filename,
        "path": target.relative_to(UPLOAD_DIR).as_posix(),
        "width": image.width,
        "height": image.height,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
