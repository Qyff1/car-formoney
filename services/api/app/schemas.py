# -*- coding: utf-8 -*-
"""请求与响应数据模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str
    role_label: str = ""


class CaseCreate(BaseModel):
    brand: str = Field(..., min_length=1, max_length=50)
    series: str = Field(..., min_length=1, max_length=50)
    vehicle_year: int | None = Field(default=None, ge=1990, le=2030)
    trim: str = Field(default="", max_length=50)
    region_code: str = Field(default="000000", max_length=20)


class CaseUpdate(BaseModel):
    brand: str | None = Field(default=None, max_length=50)
    series: str | None = Field(default=None, max_length=50)
    vehicle_year: int | None = Field(default=None, ge=1990, le=2030)
    trim: str | None = Field(default=None, max_length=50)
    region_code: str | None = Field(default=None, max_length=20)


class AnalysisRequest(BaseModel):
    case_id: int
    image_ids: list[int] | None = None
    model_version: str | None = None


class DamageUpdate(BaseModel):
    part_code: str | None = Field(default=None, max_length=50)
    part_name: str | None = Field(default=None, max_length=50)
    severity_band: str | None = Field(default=None, pattern="^(minor|medium|severe)$")
    action: str | None = Field(
        default=None,
        pattern="^(repair|paint|replace|glass_replace|lamp_replace|tire_repair|tire_replace)$",
    )
    method: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=500)
    confirmed: bool | None = None


class QuoteRequest(BaseModel):
    case_id: int
    manual_override_reason: str | None = Field(default=None, max_length=500)


class QuoteConfirmRequest(BaseModel):
    manual_override_reason: str | None = Field(default=None, max_length=500)


class ReportCreate(BaseModel):
    case_id: int
    quote_id: int


class PartPriceUpdate(BaseModel):
    price_low: float = Field(ge=0)
    list_price: float = Field(ge=0)
    price_high: float = Field(ge=0)


class LaborUpdate(BaseModel):
    standard_hours: float = Field(ge=0, le=100)


class MaterialUpdate(BaseModel):
    material_cost: float = Field(ge=0)


class RegionalRateUpdate(BaseModel):
    labor_rate: float = Field(ge=0)
    coefficient: float = Field(gt=0, le=5)


class PricingRuleUpdate(BaseModel):
    priority: int = Field(ge=0, le=1000)
    area_ratio_min: float = Field(ge=0, le=1)
    area_ratio_max: float | None = Field(default=None, ge=0, le=1)
    action: str = Field(
        pattern="^(repair|paint|replace|glass_replace|lamp_replace|tire_repair|tire_replace)$"
    )
    method: str = Field(default="", max_length=100)
    requires_review: bool = False


class TimestampedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
