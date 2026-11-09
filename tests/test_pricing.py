# -*- coding: utf-8 -*-
"""定价引擎与鉴权基础单测（隔离内存库，不触碰业务数据）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.api.app.core.pricing_engine import (
    FORMULA_TEXT,
    PricingError,
    _match_rule,
    build_quote,
    severity_suggestion,
)
from services.api.app.core.seed import seed_all
from services.api.app.db import Base
from services.api.app.models import Case, CaseImage, DamageInstance, PricingRule, SeverityThreshold
from services.api.app.security import create_access_token, decode_access_token, hash_password, verify_password


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_all(session)
    yield session
    session.close()


def _case(db, region_code="310000") -> Case:
    case = Case(
        case_no="T0001",
        brand="大众",
        series="朗逸",
        vehicle_year=2021,
        trim="舒适版",
        region_code=region_code,
        region_name="上海",
        status="pending_confirm",
        created_by_name="tester",
    )
    db.add(case)
    db.flush()
    return case


def _damage(db, case: Case, **overrides) -> DamageInstance:
    image = CaseImage(
        case_id=case.id,
        filename="t.jpg",
        original_name="t.jpg",
        path=f"cases/{case.id}/t.jpg",
        width=1000,
        height=800,
    )
    db.add(image)
    db.flush()
    payload = dict(
        case_id=case.id,
        image_id=image.id,
        class_name="scratch",
        class_id=1,
        confidence=0.9,
        bbox=[10, 10, 100, 100],
        polygons=[[[10, 10], [100, 10], [100, 100]]],
        mask_area_ratio=0.01,
        part_code="door_front",
        part_name="前车门",
        severity_band="medium",
        action="paint",
        method="局部补漆",
        confirmed=True,
    )
    payload.update(overrides)
    damage = DamageInstance(**payload)
    db.add(damage)
    db.flush()
    return damage


def test_formula_is_fixed():
    assert FORMULA_TEXT == "维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价"


def test_severity_thresholds(db):
    thresholds = db.query(SeverityThreshold).all()
    assert severity_suggestion("scratch", 0.003, thresholds) == "minor"
    assert severity_suggestion("scratch", 0.01, thresholds) == "medium"
    assert severity_suggestion("scratch", 0.03, thresholds) == "severe"


def test_rule_priority_and_part_category(db):
    rules = db.query(PricingRule).filter(PricingRule.is_current.is_(True)).all()
    assert _match_rule(rules, "scratch", None, 0.003).rule_code == "scratch_polish"
    assert _match_rule(rules, "scratch", None, 0.01).rule_code == "scratch_spot_paint"
    assert _match_rule(rules, "crack", "plastic", 0.005).rule_code == "crack_plastic_repair"
    assert _match_rule(rules, "crack", "metal", 0.005).rule_code == "crack_replace"
    assert _match_rule(rules, "glass shatter", "glass", 0.02).rule_code == "glass_replace"


def test_paint_quote_uses_material_and_labor_only(db):
    case = _case(db)
    damage = _damage(db, case)
    quote = build_quote(db, case, [damage], "tester")

    assert quote.total_mid == pytest.approx(881.45, abs=0.01)
    item = quote.items[0]
    assert item.part_price == 0
    assert item.material_cost == 200
    assert item.standard_hours == 3.5
    assert item.labor_rate == 165
    assert item.labor_coefficient == 1.18
    assert item.labor_amount == pytest.approx(681.45, abs=0.01)
    assert item.subtotal == pytest.approx(881.45, abs=0.01)
    assert quote.price_snapshot["formula"] == FORMULA_TEXT


def test_replace_quote_includes_part_price_and_range(db):
    case = _case(db)
    damage = _damage(
        db,
        case,
        class_name="tire flat",
        class_id=5,
        mask_area_ratio=0.06,
        part_code="tire",
        part_name="轮胎",
        severity_band="severe",
        action="tire_replace",
        method="轮胎更换",
    )
    quote = build_quote(db, case, [damage], "tester")

    item = quote.items[0]
    assert item.part_price == pytest.approx(903.17, abs=0.01)
    assert item.material_cost == 50
    assert item.standard_hours == 1.0
    assert item.subtotal == pytest.approx(1147.87, abs=0.01)
    assert quote.total_low < quote.total_mid < quote.total_high
    assert quote.total_mid == quote.items[0].subtotal


def test_quote_requires_part_and_confirmation(db):
    case = _case(db)
    missing_part = _damage(db, case, part_code=None, part_name=None)
    with pytest.raises(PricingError, match="受损部件"):
        build_quote(db, case, [missing_part], "tester")

    unconfirmed = _damage(db, case, confirmed=False)
    with pytest.raises(PricingError, match="人工确认"):
        build_quote(db, case, [unconfirmed], "tester")


def test_password_and_jwt_roundtrip():
    stored = hash_password("Cardd@2026")
    assert verify_password("Cardd@2026", stored)
    assert not verify_password("wrong", stored)

    token = create_access_token(7, "adjuster", "adjuster")
    payload = decode_access_token(token)
    assert payload["sub"] == "7"
    assert payload["role"] == "adjuster"
