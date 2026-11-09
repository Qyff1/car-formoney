# -*- coding: utf-8 -*-
"""初始化数据：账号、定价主数据、模型注册。"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import MODEL_VERSION_NAME, PRICING_DIR, PROJECT_ROOT
from ..models import (
    LaborStandard,
    MaterialStandard,
    ModelVersion,
    PartCatalog,
    PricingRule,
    RegionalRate,
    SeverityThreshold,
    User,
    VehicleModel,
)
from ..security import hash_password

DEFAULT_PASSWORD = "Cardd@2026"
SEED_USERS = [
    ("周显鑫0", "周显鑫0", "adjuster"),
    ("周显鑫1", "周显鑫1", "reviewer"),
    ("周显鑫2", "周显鑫2", "admin"),
]

DATASET_HASH = "db9de85f766f9cd5a5ef3234b0106f3cc2fd5b9f425ad4e7e04a38c984a03f7d"
BASELINE_RUN = "yolov8s_seg_baseline"
P2_RUN = "yolov8s_seg_p2_mask320"

# 仓库只提交两个交付权重，不提交训练产物；指标固化于此，保证全新环境初始化后
# 模型管理页能直接看到两个版本的评测结果。
METRICS_BY_RUN = {
    BASELINE_RUN: {
        "overall_mask_map50_95": 0.5611503901941586,
        "overall_mask_map50": 0.7395483180695078,
        "overall_box_map50_95": 0.5942607978991211,
        "parameters": 11792418,
        "latency_ms": {"p50": 21.3, "p95": 100.7, "mean": 35.1, "n": 50},
        "per_class_mask_ap50_95": {
            "dent": 0.32385125442684165,
            "scratch": 0.2847292728601944,
            "crack": 0.21992519320461987,
            "glass shatter": 0.8961486322040431,
            "lamp broken": 0.7464205777967596,
            "tire flat": 0.8958274106724918,
        },
    },
    P2_RUN: {
        "overall_mask_map50_95": 0.5536445606998328,
        "overall_mask_map50": 0.7245663110151804,
        "overall_box_map50_95": 0.5835844045563581,
        "parameters": 11248136,
        "latency_ms": {"p50": 27.4, "p95": 94.7, "mean": 38.9, "n": 50},
        "per_class_mask_ap50_95": {
            "dent": 0.320214388113675,
            "scratch": 0.26368854048966794,
            "crack": 0.2069617334613425,
            "glass shatter": 0.912312137260361,
            "lamp broken": 0.7417014552941092,
            "tire flat": 0.8769891095798409,
        },
    },
}
# 模型库：基线与 P2 改进版同时入库，供模型管理页选择启用
MODEL_LIBRARY = [
    {
        "name": MODEL_VERSION_NAME,
        "run": BASELINE_RUN,
        "train_config": {"model": "yolov8s-seg.pt", "imgsz": 640, "epochs": 200, "batch": 3,
                         "patience": 50, "seed": 42, "close_mosaic": 15, "cos_lr": True,
                         "workers": 0, "mask_ratio": 4},
    },
    {
        "name": "yolov8s-seg-p2-mask320",
        "run": P2_RUN,
        "train_config": {"model": "yolov8s-seg-p2.yaml", "imgsz": 640, "epochs": 200, "batch": 2,
                         "seed": 42, "close_mosaic": 15, "cos_lr": True, "workers": 0,
                         "mask_ratio": 2},
    },
]


def _load(name: str) -> dict:
    return json.loads((PRICING_DIR / name).read_text(encoding="utf-8"))


def _seed_users(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    for username, full_name, role in SEED_USERS:
        db.add(
            User(
                username=username,
                password_hash=hash_password(DEFAULT_PASSWORD),
                full_name=full_name,
                role=role,
            )
        )


def _seed_vehicle_models(db: Session) -> None:
    if db.query(VehicleModel).count() > 0:
        return
    for item in _load("vehicle_models.json")["items"]:
        db.add(
            VehicleModel(
                code=item["code"],
                brand=item["brand"],
                series=item["series"],
                year_from=item["year_from"],
                year_to=item["year_to"],
                trim=item["trim"],
                is_default=item["is_default"],
            )
        )


def _seed_parts(db: Session) -> None:
    """按年款逐年生成配件价格。

    同一车型以年款区间最新年为基准价，车龄每增加一年乘 annual_factor，
    最低保留 floor，配置见 pricing_rules.json 的 vehicle_year_pricing。
    """
    per_year = (
        db.query(PartCatalog)
        .filter(PartCatalog.vehicle_model_id.isnot(None), PartCatalog.vehicle_year.isnot(None))
        .count()
    )
    if per_year > 0:
        return

    db.query(PartCatalog).filter(PartCatalog.vehicle_model_id.isnot(None)).delete(
        synchronize_session=False
    )
    has_generic = db.query(PartCatalog).filter(PartCatalog.vehicle_model_id.is_(None)).count() > 0
    vehicles = {row.code: row for row in db.query(VehicleModel).all()}
    policy = _load("pricing_rules.json").get("vehicle_year_pricing") or {}
    annual_factor = float(policy.get("annual_factor", 0.96))
    floor = float(policy.get("floor", 0.65))

    for item in _load("part_catalog.json")["items"]:
        code = item["vehicle_model_code"]
        if code == "generic":
            if has_generic:
                continue
            vehicle, years = None, [None]
        else:
            vehicle = vehicles.get(code)
            if vehicle is None:
                continue
            years = range(vehicle.year_from, vehicle.year_to + 1)
        for year in years:
            factor = 1.0 if year is None else max(floor, annual_factor ** (vehicle.year_to - year))
            db.add(
                PartCatalog(
                    vehicle_model_id=None if vehicle is None else vehicle.id,
                    vehicle_year=year,
                    part_code=item["part_code"],
                    part_name=item["part_name"],
                    category=item["category"],
                    paintable=item["paintable"],
                    replaceable=item["replaceable"],
                    price_low=round(item["price_low"] * factor, 2),
                    list_price=round(item["list_price"] * factor, 2),
                    price_high=round(item["price_high"] * factor, 2),
                )
            )


def _seed_labor(db: Session) -> None:
    if db.query(LaborStandard).count() > 0:
        return
    for item in _load("labor_standard.json")["items"]:
        db.add(
            LaborStandard(
                part_code=item["part_code"],
                damage_type=item["damage_type"],
                action=item["action"],
                severity_band=item["severity_band"],
                standard_hours=item["standard_hours"],
            )
        )


def _seed_material(db: Session) -> None:
    if db.query(MaterialStandard).count() > 0:
        return
    for item in _load("material_standard.json")["items"]:
        db.add(
            MaterialStandard(
                part_code=item["part_code"],
                action=item["action"],
                severity_band=item["severity_band"],
                material_cost=item["material_cost"],
            )
        )


def _seed_regions(db: Session) -> None:
    if db.query(RegionalRate).count() > 0:
        return
    for item in _load("regional_rate.json")["items"]:
        db.add(
            RegionalRate(
                region_code=item["region_code"],
                region_name=item["region_name"],
                labor_rate=item["labor_rate"],
                coefficient=item["coefficient"],
            )
        )


def _seed_rules(db: Session) -> None:
    payload = _load("pricing_rules.json")
    version = int(payload.get("version", 1))
    if db.query(PricingRule).count() == 0:
        for item in payload["rules"]:
            db.add(
                PricingRule(
                    rule_code=item["rule_code"],
                    priority=item["priority"],
                    damage_type=item["damage_type"],
                    part_category=item["part_category"],
                    area_ratio_min=item["area_ratio_min"],
                    area_ratio_max=item["area_ratio_max"],
                    action=item["action"],
                    method=item["method"],
                    requires_review=item["requires_review"],
                    formula_version=payload["formula_version"],
                    version=version,
                )
            )
    else:
        # 规则文件升级后，同步已有规则的版本号，报价快照据此记录规则版本
        db.query(PricingRule).filter(PricingRule.version != version).update(
            {PricingRule.version: version}, synchronize_session=False
        )
    if db.query(SeverityThreshold).count() == 0:
        for item in payload["severity_thresholds"]:
            db.add(
                SeverityThreshold(
                    damage_type=item["damage_type"],
                    minor_max=item["minor_max"],
                    severe_min=item["severe_min"],
                )
            )


def _load_model_metrics(run: str) -> dict | None:
    verify_file = PROJECT_ROOT / "runs" / "cardd" / run / "verify" / "results.json"
    if not Path(verify_file).exists():
        return METRICS_BY_RUN.get(run)
    data = json.loads(verify_file.read_text(encoding="utf-8"))
    return {
        "overall_mask_map50_95": data.get("overall_mask_map50_95"),
        "overall_mask_map50": data.get("overall_mask_map50"),
        "overall_box_map50_95": data.get("overall_box_map50_95"),
        "per_class_mask_ap50_95": data.get("per_class_mask_ap50_95"),
        "parameters": data.get("parameters"),
        "latency_ms": data.get("latency_ms"),
    }


def _seed_model(db: Session) -> None:
    has_active = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).count() > 0
    for index, spec in enumerate(MODEL_LIBRARY):
        row = db.query(ModelVersion).filter(ModelVersion.name == spec["name"]).first()
        metrics = _load_model_metrics(spec["run"])
        if row is None:
            db.add(
                ModelVersion(
                    name=spec["name"],
                    weights_path=str(PROJECT_ROOT / "runs" / "cardd" / spec["run"] / "weights" / "best.pt"),
                    metrics=metrics,
                    train_config=spec["train_config"],
                    dataset_hash=DATASET_HASH,
                    is_active=index == 0 and not has_active,
                )
            )
            continue
        if not row.metrics and metrics:
            row.metrics = metrics
        if not row.train_config:
            row.train_config = spec["train_config"]
        if not row.dataset_hash:
            row.dataset_hash = DATASET_HASH


def seed_all(db: Session) -> None:
    _seed_users(db)
    _seed_vehicle_models(db)
    _seed_parts(db)
    _seed_labor(db)
    _seed_material(db)
    _seed_regions(db)
    _seed_rules(db)
    _seed_model(db)
    db.commit()
