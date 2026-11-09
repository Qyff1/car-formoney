# -*- coding: utf-8 -*-
"""定损报告（F6）。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..config import REPORT_DIR
from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Case, CaseImage, DamageInstance, ModelVersion, Quote, Report, User
from ..schemas import ReportCreate
from ..core.numbers import next_number
from ..core.report_builder import build_report_html

router = APIRouter(prefix="/api", tags=["reports"])


def _report_dict(report: Report) -> dict:
    return {
        "id": report.id,
        "report_no": report.report_no,
        "case_id": report.case_id,
        "quote_id": report.quote_id,
        "html_url": f"/api/reports/{report.id}/html",
        "file_url": f"/files/{report.html_path}",
        "generated_by": report.generated_by,
        "generated_at": report.generated_at,
    }


@router.post("/reports")
def create_report(payload: ReportCreate, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("adjuster", "admin"))):
    case = db.get(Case, payload.case_id)
    quote = db.get(Quote, payload.quote_id)
    if case is None or quote is None:
        raise HTTPException(status_code=404, detail="案件或报价不存在")
    if quote.case_id != case.id:
        raise HTTPException(status_code=400, detail="报价不属于该案件")
    if quote.status != "confirmed":
        raise HTTPException(status_code=409, detail="报价尚未确认，不能生成报告")

    images = db.query(CaseImage).filter(CaseImage.case_id == case.id).order_by(CaseImage.id).all()
    damages = db.query(DamageInstance).filter(
        DamageInstance.case_id == case.id
    ).order_by(DamageInstance.id).all()
    model = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
    default_model = model.name if model else "yolov8s-seg-baseline"
    used_models = sorted({image.model_name for image in images if image.model_name})
    model_name = "、".join(used_models) or default_model

    report_no = next_number(db, Report, Report.report_no, "R")
    generated_at = datetime.now()
    html_text = build_report_html(case, quote, images, damages, report_no, model_name, generated_at)
    target = REPORT_DIR / f"{report_no}.html"
    target.write_text(html_text, encoding="utf-8")

    report = Report(
        report_no=report_no,
        case_id=case.id,
        quote_id=quote.id,
        html_path=target.relative_to(REPORT_DIR.parent).as_posix(),
        generated_by=user.full_name or user.username,
        generated_at=generated_at,
    )
    db.add(report)
    case.status = "reported"
    db.flush()
    record_audit(db, user, "create_report", "report", report.id,
                 {"case_id": case.id, "quote_id": quote.id})
    db.commit()
    db.refresh(report)
    return _report_dict(report)


@router.get("/cases/{case_id}/reports")
def list_reports(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).all()
    return [_report_dict(r) for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return _report_dict(report)


@router.get("/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: int, db: Session = Depends(get_db),
                    _: User = Depends(get_current_user)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    path = REPORT_DIR.parent / report.html_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="报告文件已丢失，请重新生成")
    return HTMLResponse(content=path.read_text(encoding="utf-8"))
