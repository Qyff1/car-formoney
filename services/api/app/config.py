# -*- coding: utf-8 -*-
"""全局配置：路径、认证、推理参数。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CASE_FILE_DIR = UPLOAD_DIR / "cases"
OVERLAY_DIR = UPLOAD_DIR / "overlays"
REPORT_DIR = UPLOAD_DIR / "reports"
PRICING_DIR = PROJECT_ROOT / "config" / "pricing"

DB_PATH = Path(os.getenv("APP_DB_PATH", str(DATA_DIR / "app.db")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CASE_FILE_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

JWT_SECRET = os.getenv("APP_JWT_SECRET", "car-formoney-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("APP_JWT_EXPIRE_MINUTES", "480"))

# 线上模型：按技术方案采用准则，P2 未达标，保留基线
DEFAULT_WEIGHTS = PROJECT_ROOT / "runs" / "cardd" / "yolov8s_seg_baseline" / "weights" / "best.pt"
MODEL_VERSION_NAME = os.getenv("APP_MODEL_VERSION", "yolov8s-seg-baseline")
INFER_IMGSZ = int(os.getenv("APP_INFER_IMGSZ", "640"))
INFER_CONF = float(os.getenv("APP_INFER_CONF", "0.25"))
INFER_IOU = float(os.getenv("APP_INFER_IOU", "0.7"))
REVIEW_CONFIDENCE = float(os.getenv("APP_REVIEW_CONFIDENCE", "0.5"))
INFER_DEVICE = os.getenv("APP_INFER_DEVICE", "0")

MAX_UPLOAD_MB = int(os.getenv("APP_MAX_UPLOAD_MB", "20"))
MAX_IMAGES_PER_CASE = int(os.getenv("APP_MAX_IMAGES_PER_CASE", "10"))
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CASE_STATUS = {
    "draft": "草稿",
    "analyzing": "分析中",
    "pending_confirm": "待确认",
    "quoted": "已报价",
    "reported": "已出报告",
}

ROLE_LABELS = {
    "adjuster": "查勘定损员",
    "reviewer": "审核员",
    "admin": "系统管理员",
}
