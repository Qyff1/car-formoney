# -*- coding: utf-8 -*-
"""ORM 模型：主数据、业务表、审计与模型注册。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .db import Base


def now() -> datetime:
    return datetime.now()


# ------------------------- 账号与审计 -------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(50), nullable=False, default="")
    role = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=False, default="")
    role = Column(String(20), nullable=False, default="")
    action = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, default="")
    entity_id = Column(String(50), nullable=False, default="")
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now, index=True)


# ------------------------- 定价主数据 -------------------------

class VehicleModel(Base):
    __tablename__ = "vehicle_model"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    brand = Column(String(50), nullable=False)
    series = Column(String(50), nullable=False)
    year_from = Column(Integer, nullable=False)
    year_to = Column(Integer, nullable=False)
    trim = Column(String(50), nullable=False, default="")
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)


class PartCatalog(Base):
    __tablename__ = "part_catalog"

    id = Column(Integer, primary_key=True)
    vehicle_model_id = Column(Integer, ForeignKey("vehicle_model.id"), nullable=True, index=True)
    vehicle_year = Column(Integer, nullable=True, index=True)
    part_code = Column(String(50), nullable=False, index=True)
    part_name = Column(String(50), nullable=False)
    category = Column(String(20), nullable=False, default="metal")
    paintable = Column(Boolean, nullable=False, default=False)
    replaceable = Column(Boolean, nullable=False, default=False)
    price_low = Column(Float, nullable=False, default=0)
    list_price = Column(Float, nullable=False, default=0)
    price_high = Column(Float, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="CNY")
    effective_from = Column(Date, nullable=False, default=date.today)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=now)


class LaborStandard(Base):
    __tablename__ = "labor_standard"

    id = Column(Integer, primary_key=True)
    part_code = Column(String(50), nullable=True, index=True)
    damage_type = Column(String(50), nullable=True)
    action = Column(String(30), nullable=False, index=True)
    severity_band = Column(String(20), nullable=False, index=True)
    standard_hours = Column(Float, nullable=False, default=0)
    effective_from = Column(Date, nullable=False, default=date.today)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)


class MaterialStandard(Base):
    __tablename__ = "material_standard"

    id = Column(Integer, primary_key=True)
    part_code = Column(String(50), nullable=True, index=True)
    action = Column(String(30), nullable=False, index=True)
    severity_band = Column(String(20), nullable=False, index=True)
    material_cost = Column(Float, nullable=False, default=0)
    effective_from = Column(Date, nullable=False, default=date.today)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)


class RegionalRate(Base):
    __tablename__ = "regional_rate"

    id = Column(Integer, primary_key=True)
    region_code = Column(String(20), nullable=False, index=True)
    region_name = Column(String(50), nullable=False)
    labor_rate = Column(Float, nullable=False)
    coefficient = Column(Float, nullable=False, default=1.0)
    effective_from = Column(Date, nullable=False, default=date.today)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)


class PricingRule(Base):
    __tablename__ = "pricing_rule"

    id = Column(Integer, primary_key=True)
    rule_code = Column(String(50), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=0)
    damage_type = Column(String(50), nullable=False, index=True)
    part_category = Column(JSON, nullable=True)
    area_ratio_min = Column(Float, nullable=False, default=0)
    area_ratio_max = Column(Float, nullable=True)
    action = Column(String(30), nullable=False)
    method = Column(String(100), nullable=False, default="")
    requires_review = Column(Boolean, nullable=False, default=False)
    formula_version = Column(String(50), nullable=False, default="v1")
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)


class SeverityThreshold(Base):
    __tablename__ = "severity_threshold"

    id = Column(Integer, primary_key=True)
    damage_type = Column(String(50), nullable=False, index=True)
    minor_max = Column(Float, nullable=False)
    severe_min = Column(Float, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True, index=True)


# ------------------------- 业务表 -------------------------

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True)
    case_no = Column(String(40), unique=True, nullable=False, index=True)
    brand = Column(String(50), nullable=False, default="")
    series = Column(String(50), nullable=False, default="")
    vehicle_year = Column(Integer, nullable=True)
    trim = Column(String(50), nullable=False, default="")
    region_code = Column(String(20), nullable=False, default="000000")
    region_name = Column(String(50), nullable=False, default="全国参考")
    status = Column(String(20), nullable=False, default="draft", index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_name = Column(String(50), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=now, index=True)
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now)

    images = relationship("CaseImage", back_populates="case", cascade="all, delete-orphan")
    damages = relationship("DamageInstance", back_populates="case", cascade="all, delete-orphan")


class CaseImage(Base):
    __tablename__ = "case_image"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    filename = Column(String(200), nullable=False)
    original_name = Column(String(200), nullable=False, default="")
    path = Column(String(500), nullable=False)
    overlay_path = Column(String(500), nullable=True)
    width = Column(Integer, nullable=False, default=0)
    height = Column(Integer, nullable=False, default=0)
    sha256 = Column(String(64), nullable=False, default="")
    model_name = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=now)

    case = relationship("Case", back_populates="images")
    damages = relationship("DamageInstance", back_populates="image", cascade="all, delete-orphan")


class DamageInstance(Base):
    __tablename__ = "damage_instance"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    image_id = Column(Integer, ForeignKey("case_image.id"), nullable=False, index=True)
    class_name = Column(String(50), nullable=False, index=True)
    class_id = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0)
    bbox = Column(JSON, nullable=False)
    polygons = Column(JSON, nullable=False)
    mask_area_ratio = Column(Float, nullable=False, default=0)
    needs_review = Column(Boolean, nullable=False, default=False)
    part_code = Column(String(50), nullable=True)
    part_name = Column(String(50), nullable=True)
    severity_band = Column(String(20), nullable=True)
    action = Column(String(30), nullable=True)
    method = Column(String(100), nullable=True)
    note = Column(String(500), nullable=True)
    confirmed = Column(Boolean, nullable=False, default=False)
    confirmed_by = Column(String(50), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now)

    case = relationship("Case", back_populates="damages")
    image = relationship("CaseImage", back_populates="damages")


class Quote(Base):
    __tablename__ = "price_quote"

    id = Column(Integer, primary_key=True)
    quote_no = Column(String(40), unique=True, nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    pricing_rule_version = Column(Integer, nullable=False, default=1)
    formula_version = Column(String(50), nullable=False, default="v1")
    status = Column(String(20), nullable=False, default="draft", index=True)
    total_low = Column(Float, nullable=False, default=0)
    total_mid = Column(Float, nullable=False, default=0)
    total_high = Column(Float, nullable=False, default=0)
    region_code = Column(String(20), nullable=False, default="000000")
    region_name = Column(String(50), nullable=False, default="全国参考")
    labor_rate = Column(Float, nullable=False, default=0)
    labor_coefficient = Column(Float, nullable=False, default=1.0)
    price_snapshot = Column(JSON, nullable=False)
    hit_rules = Column(JSON, nullable=False)
    manual_override_reason = Column(String(500), nullable=True)
    created_by_name = Column(String(50), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=now)
    confirmed_by = Column(String(50), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    items = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")


class QuoteItem(Base):
    __tablename__ = "price_quote_item"

    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey("price_quote.id"), nullable=False, index=True)
    damage_id = Column(Integer, ForeignKey("damage_instance.id"), nullable=True)
    part_code = Column(String(50), nullable=False)
    part_name = Column(String(50), nullable=False)
    action = Column(String(30), nullable=False)
    method = Column(String(100), nullable=False, default="")
    severity_band = Column(String(20), nullable=False)
    part_price = Column(Float, nullable=False, default=0)
    material_cost = Column(Float, nullable=False, default=0)
    standard_hours = Column(Float, nullable=False, default=0)
    labor_rate = Column(Float, nullable=False, default=0)
    labor_coefficient = Column(Float, nullable=False, default=1.0)
    labor_amount = Column(Float, nullable=False, default=0)
    subtotal_low = Column(Float, nullable=False, default=0)
    subtotal = Column(Float, nullable=False, default=0)
    subtotal_high = Column(Float, nullable=False, default=0)
    rule_code = Column(String(50), nullable=False, default="")
    requires_review = Column(Boolean, nullable=False, default=False)
    note = Column(String(500), nullable=True)

    quote = relationship("Quote", back_populates="items")


class Report(Base):
    __tablename__ = "report"

    id = Column(Integer, primary_key=True)
    report_no = Column(String(40), unique=True, nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    quote_id = Column(Integer, ForeignKey("price_quote.id"), nullable=False, index=True)
    html_path = Column(String(500), nullable=False)
    generated_by = Column(String(50), nullable=False, default="")
    generated_at = Column(DateTime, nullable=False, default=now)


class ModelVersion(Base):
    __tablename__ = "model_version"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    weights_path = Column(String(500), nullable=False)
    metrics = Column(JSON, nullable=True)
    train_config = Column(JSON, nullable=True)
    dataset_hash = Column(String(64), nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=now)
