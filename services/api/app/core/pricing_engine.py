# -*- coding: utf-8 -*-
"""规则定价引擎。

公式（既定，不得修改）：
    维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价

维修动作由“损伤类型 + 受损部件 + 损伤面积/严重度 + 人工确认”共同决定：
本模块只给出规则初判建议，人工确认后的字段优先级更高。报价结果保存完整
价格快照与命中规则，保证主数据变更后仍可复算。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import PRICING_DIR
from ..models import (
    Case,
    DamageInstance,
    LaborStandard,
    MaterialStandard,
    PartCatalog,
    PricingRule,
    Quote,
    QuoteItem,
    RegionalRate,
    SeverityThreshold,
    VehicleModel,
)

FORMULA_TEXT = "维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价"
REPLACE_ACTIONS = {"replace", "glass_replace", "lamp_replace", "tire_replace"}

SEVERITY_LABELS = {"minor": "轻微", "medium": "一般", "severe": "严重"}
ACTION_LABELS = {
    "repair": "维修",
    "paint": "喷漆",
    "replace": "更换",
    "glass_replace": "玻璃更换",
    "lamp_replace": "灯总成更换",
    "tire_repair": "补胎",
    "tire_replace": "轮胎更换",
}
DAMAGE_LABELS = {
    "dent": "凹陷",
    "scratch": "刮擦",
    "crack": "裂纹",
    "glass shatter": "玻璃破碎",
    "lamp broken": "车灯破损",
    "tire flat": "轮胎损伤",
}

# 模型只识别损伤类型，不识别具体部件；分析后按规则文件预填部件作为系统初判
_DEFAULT_PART_RULES = json.loads(
    (PRICING_DIR / "pricing_rules.json").read_text(encoding="utf-8")
).get("default_parts", {})


def default_part_for_class(class_name: str) -> str | None:
    """按损伤类型返回预填的受损部件编码，未配置时返回 None。"""
    value = _DEFAULT_PART_RULES.get(class_name)
    return value if isinstance(value, str) else None


class PricingError(Exception):
    """定价输入不完整或主数据缺失。"""


def severity_suggestion(damage_type: str, area_ratio: float, thresholds: list[SeverityThreshold]) -> str:
    rule = next((t for t in thresholds if t.damage_type == damage_type), None)
    if rule is None:
        return "medium"
    if area_ratio <= rule.minor_max:
        return "minor"
    if area_ratio >= rule.severe_min:
        return "severe"
    return "medium"


def _match_rule(
    rules: list[PricingRule],
    damage_type: str,
    part_category: str | None,
    area_ratio: float,
) -> PricingRule | None:
    candidates = []
    for rule in rules:
        if rule.damage_type != damage_type:
            continue
        if rule.part_category and part_category not in rule.part_category:
            continue
        if area_ratio < rule.area_ratio_min:
            continue
        if rule.area_ratio_max is not None and area_ratio >= rule.area_ratio_max:
            continue
        candidates.append(rule)
    if not candidates:
        return None
    candidates.sort(key=lambda r: (-r.priority, r.id))
    return candidates[0]


def _pick_part(
    db: Session,
    part_code: str,
    vehicle_model: VehicleModel | None,
    vehicle_year: int | None = None,
) -> PartCatalog | None:
    rows = (
        db.query(PartCatalog)
        .filter(PartCatalog.part_code == part_code, PartCatalog.is_current.is_(True))
        .all()
    )
    if not rows:
        return None
    if vehicle_model is not None:
        # 优先命中该车型对应年款的专属价，其次回退到车系级价格
        if vehicle_year is not None:
            exact = next(
                (r for r in rows
                 if r.vehicle_model_id == vehicle_model.id and r.vehicle_year == vehicle_year),
                None,
            )
            if exact is not None:
                return exact
        specific = next(
            (r for r in rows if r.vehicle_model_id == vehicle_model.id and r.vehicle_year is None),
            None,
        )
        if specific is not None:
            return specific
    generic = next((r for r in rows if r.vehicle_model_id is None), None)
    return generic or rows[0]


def _pick_labor(
    db: Session,
    part_code: str,
    damage_type: str,
    action: str,
    severity: str,
    vehicle_model: VehicleModel | None,
) -> LaborStandard | None:
    rows = (
        db.query(LaborStandard)
        .filter(
            LaborStandard.action == action,
            LaborStandard.severity_band == severity,
            LaborStandard.is_current.is_(True),
        )
        .all()
    )
    if not rows:
        return None

    def score(row: LaborStandard) -> int:
        value = 0
        if row.part_code == part_code:
            value += 4
        elif row.part_code is not None:
            return -1
        if row.damage_type == damage_type:
            value += 2
        elif row.damage_type is not None:
            return -1
        return value

    scored = [(score(r), r) for r in rows]
    scored = [(s, r) for s, r in scored if s >= 0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return scored[0][1]


def _pick_material(db: Session, part_code: str, action: str, severity: str) -> MaterialStandard | None:
    rows = (
        db.query(MaterialStandard)
        .filter(
            MaterialStandard.action == action,
            MaterialStandard.severity_band == severity,
            MaterialStandard.is_current.is_(True),
        )
        .all()
    )
    if not rows:
        return None
    specific = next((r for r in rows if r.part_code == part_code), None)
    if specific is not None:
        return specific
    return next((r for r in rows if r.part_code is None), None)


def _pick_rate(db: Session, region_code: str) -> RegionalRate:
    row = (
        db.query(RegionalRate)
        .filter(RegionalRate.region_code == region_code, RegionalRate.is_current.is_(True))
        .first()
    )
    if row is None:
        row = (
            db.query(RegionalRate)
            .filter(RegionalRate.region_code == "000000", RegionalRate.is_current.is_(True))
            .first()
        )
    if row is None:
        raise PricingError("地区工时单价主数据缺失，请先初始化 regional_rate")
    return row


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[\s\-_·]+", "", (value or "")).lower()


def _pick_vehicle_model(db: Session, case: Case) -> VehicleModel | None:
    """按用户填写的品牌、车系、年款匹配车型主数据，匹配不到则返回 None。"""
    rows = (
        db.query(VehicleModel)
        .filter(VehicleModel.is_active.is_(True))
        .order_by(VehicleModel.id)
        .all()
    )
    brand = _normalize_name(case.brand)
    series = _normalize_name(case.series)
    if not brand or not series:
        return None

    def same(left: str, right: str) -> bool:
        return left == right or left in right or right in left

    matched = [
        row
        for row in rows
        if same(brand, _normalize_name(row.brand)) and same(series, _normalize_name(row.series))
    ]
    if not matched:
        return None
    if case.vehicle_year:
        covering = [row for row in matched if row.year_from <= case.vehicle_year <= row.year_to]
        matched = covering or matched
    return matched[0]


def suggest_damage(db: Session, damage: DamageInstance) -> dict:
    """给出严重度与维修动作建议（不落库），供工作台展示。"""
    thresholds = db.query(SeverityThreshold).filter(SeverityThreshold.is_current.is_(True)).all()
    rules = db.query(PricingRule).filter(PricingRule.is_current.is_(True)).all()
    severity = severity_suggestion(damage.class_name, damage.mask_area_ratio, thresholds)
    part = _pick_part(db, damage.part_code, None) if damage.part_code else None
    category = part.category if part else None
    rule = _match_rule(rules, damage.class_name, category, damage.mask_area_ratio)
    return {
        "severity_band": severity,
        "severity_label": SEVERITY_LABELS.get(severity, severity),
        "action": rule.action if rule else None,
        "action_label": ACTION_LABELS.get(rule.action, rule.action) if rule else None,
        "method": rule.method if rule else None,
        "rule_code": rule.rule_code if rule else None,
        "requires_review": (rule.requires_review if rule else True) or damage.needs_review,
    }


def build_quote(db: Session, case: Case, damages: list[DamageInstance], created_by_name: str) -> Quote:
    """按当前主数据与人工确认字段生成报价（不落库）。"""
    if not damages:
        raise PricingError("案件没有损伤实例，无法报价")

    missing = [d.id for d in damages if not d.part_code]
    if missing:
        raise PricingError(f"以下损伤实例尚未确认受损部件：{missing}")

    unconfirmed = [d.id for d in damages if not d.confirmed]
    if unconfirmed:
        raise PricingError(f"以下损伤实例尚未完成人工确认：{unconfirmed}")

    rules = db.query(PricingRule).filter(PricingRule.is_current.is_(True)).all()
    thresholds = db.query(SeverityThreshold).filter(SeverityThreshold.is_current.is_(True)).all()
    rate = _pick_rate(db, case.region_code)
    vehicle_model = _pick_vehicle_model(db, case)

    items: list[QuoteItem] = []
    snapshots: list[dict] = []
    hit_rules: list[dict] = []

    for damage in damages:
        part = _pick_part(db, damage.part_code, vehicle_model, case.vehicle_year)
        if part is None:
            raise PricingError(f"部件 {damage.part_code} 未在配件目录中配置")

        severity = damage.severity_band or severity_suggestion(
            damage.class_name, damage.mask_area_ratio, thresholds
        )

        if damage.action:
            action = damage.action
            method = damage.method or ACTION_LABELS.get(action, action)
            rule_code = "manual"
            requires_review = bool(damage.needs_review)
        else:
            rule = _match_rule(rules, damage.class_name, part.category, damage.mask_area_ratio)
            if rule is None:
                action = "repair"
                method = "人工确认维修方式"
                rule_code = "fallback_manual"
                requires_review = True
            else:
                action = rule.action
                method = rule.method
                rule_code = rule.rule_code
                requires_review = rule.requires_review or bool(damage.needs_review)

        part_price = 0.0
        part_price_low = 0.0
        part_price_high = 0.0
        price_band = "none"
        if action in REPLACE_ACTIONS:
            if not part.replaceable:
                raise PricingError(f"部件 {part.part_name} 不支持更换动作")
            # 更换类配件按严重度取低/中/高位价：轻微→低位、一般→中位、严重→高位
            band_price = {"minor": part.price_low, "medium": part.list_price, "severe": part.price_high}
            price_band = severity
            part_price = float(band_price.get(severity, part.list_price))
            part_price_low = float(part.price_low)
            part_price_high = float(part.price_high)

        material_row = _pick_material(db, part.part_code, action, severity)
        material_cost = float(material_row.material_cost) if material_row else 0.0

        labor_row = _pick_labor(db, part.part_code, damage.class_name, action, severity, vehicle_model)
        standard_hours = float(labor_row.standard_hours) if labor_row else 0.0

        labor_amount = round(standard_hours * float(rate.labor_rate) * float(rate.coefficient), 2)
        subtotal = round(part_price + material_cost + labor_amount, 2)
        subtotal_low = round(part_price_low + material_cost * 0.9 + labor_amount * 0.9, 2)
        subtotal_high = round(part_price_high + material_cost * 1.15 + labor_amount * 1.15, 2)

        item = QuoteItem(
            damage_id=damage.id,
            part_code=part.part_code,
            part_name=part.part_name,
            action=action,
            method=method,
            severity_band=severity,
            part_price=round(part_price, 2),
            material_cost=round(material_cost, 2),
            standard_hours=standard_hours,
            labor_rate=float(rate.labor_rate),
            labor_coefficient=float(rate.coefficient),
            labor_amount=labor_amount,
            subtotal_low=subtotal_low,
            subtotal=subtotal,
            subtotal_high=subtotal_high,
            rule_code=rule_code,
            requires_review=requires_review,
            note=damage.note,
        )
        items.append(item)
        hit_rules.append(
            {
                "damage_id": damage.id,
                "class_name": damage.class_name,
                "part_code": part.part_code,
                "area_ratio": round(damage.mask_area_ratio, 6),
                "severity_band": severity,
                "action": action,
                "method": method,
                "rule_code": rule_code,
                "requires_review": requires_review,
            }
        )
        snapshots.append(
            {
                "damage_id": damage.id,
                "class_name": damage.class_name,
                "confidence": round(damage.confidence, 4),
                "part_code": part.part_code,
                "part_name": part.part_name,
                "part_category": part.category,
                "vehicle_year": case.vehicle_year,
                "part_catalog_year": part.vehicle_year,
                "price_band": price_band,
                "severity_band": severity,
                "action": action,
                "method": method,
                "rule_code": rule_code,
                "price_low": part.price_low if action in REPLACE_ACTIONS else 0,
                "list_price": part.list_price if action in REPLACE_ACTIONS else 0,
                "price_high": part.price_high if action in REPLACE_ACTIONS else 0,
                "material_cost": material_cost,
                "standard_hours": standard_hours,
                "labor_rate": float(rate.labor_rate),
                "labor_coefficient": float(rate.coefficient),
                "subtotal_low": subtotal_low,
                "subtotal": subtotal,
                "subtotal_high": subtotal_high,
            }
        )

    total_low = round(sum(i.subtotal_low for i in items), 2)
    total_mid = round(sum(i.subtotal for i in items), 2)
    total_high = round(sum(i.subtotal_high for i in items), 2)
    rule_version = max((r.version for r in rules), default=1)
    formula_version = rules[0].formula_version if rules else "v1"

    quote = Quote(
        quote_no="",
        case_id=case.id,
        pricing_rule_version=rule_version,
        formula_version=formula_version,
        status="draft",
        total_low=total_low,
        total_mid=total_mid,
        total_high=total_high,
        region_code=rate.region_code,
        region_name=rate.region_name,
        labor_rate=float(rate.labor_rate),
        labor_coefficient=float(rate.coefficient),
        price_snapshot={
            "formula": FORMULA_TEXT,
            "formula_version": formula_version,
            "pricing_rule_version": rule_version,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "region": {
                "region_code": rate.region_code,
                "region_name": rate.region_name,
                "labor_rate": float(rate.labor_rate),
                "coefficient": float(rate.coefficient),
            },
            "vehicle": {
                "brand": case.brand,
                "series": case.series,
                "vehicle_year": case.vehicle_year,
                "trim": case.trim,
            },
            "items": snapshots,
        },
        hit_rules=hit_rules,
        created_by_name=created_by_name,
    )
    quote.items = items
    return quote


def quote_to_dict(quote: Quote) -> dict:
    return {
        "id": quote.id,
        "quote_no": quote.quote_no,
        "case_id": quote.case_id,
        "pricing_rule_version": quote.pricing_rule_version,
        "formula_version": quote.formula_version,
        "status": quote.status,
        "total_low": quote.total_low,
        "total_mid": quote.total_mid,
        "total_high": quote.total_high,
        "region_code": quote.region_code,
        "region_name": quote.region_name,
        "labor_rate": quote.labor_rate,
        "labor_coefficient": quote.labor_coefficient,
        "manual_override_reason": quote.manual_override_reason,
        "created_by_name": quote.created_by_name,
        "created_at": quote.created_at,
        "confirmed_by": quote.confirmed_by,
        "confirmed_at": quote.confirmed_at,
        "hit_rules": quote.hit_rules,
        "items": [
            {
                "id": i.id,
                "damage_id": i.damage_id,
                "part_code": i.part_code,
                "part_name": i.part_name,
                "action": i.action,
                "action_label": ACTION_LABELS.get(i.action, i.action),
                "method": i.method,
                "severity_band": i.severity_band,
                "severity_label": SEVERITY_LABELS.get(i.severity_band, i.severity_band),
                "part_price": i.part_price,
                "material_cost": i.material_cost,
                "standard_hours": i.standard_hours,
                "labor_rate": i.labor_rate,
                "labor_coefficient": i.labor_coefficient,
                "labor_amount": i.labor_amount,
                "subtotal_low": i.subtotal_low,
                "subtotal": i.subtotal,
                "subtotal_high": i.subtotal_high,
                "rule_code": i.rule_code,
                "requires_review": i.requires_review,
                "note": i.note,
            }
            for i in quote.items
        ],
    }
