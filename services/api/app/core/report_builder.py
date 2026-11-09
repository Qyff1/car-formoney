# -*- coding: utf-8 -*-
"""定损报告生成（HTML，可浏览器打印为 PDF）。"""
from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

from ..config import UPLOAD_DIR
from ..models import Case, CaseImage, DamageInstance, Quote
from .pricing_engine import ACTION_LABELS, DAMAGE_LABELS, FORMULA_TEXT, SEVERITY_LABELS


def _b64(path: str, mime: str) -> str:
    data = Path(UPLOAD_DIR / path).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _mime(path: str) -> str:
    return "image/png" if path.lower().endswith(".png") else "image/jpeg"


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def build_report_html(
    case: Case,
    quote: Quote,
    images: list[CaseImage],
    damages: list[DamageInstance],
    report_no: str,
    model_name: str,
    generated_at: datetime,
) -> str:
    items_by_damage = {item.damage_id: item for item in quote.items}
    damage_by_image: dict[int, list[DamageInstance]] = {}
    for damage in damages:
        damage_by_image.setdefault(damage.image_id, []).append(damage)

    image_blocks = []
    for image in images:
        original = _b64(image.path, _mime(image.path))
        overlay = _b64(image.overlay_path, _mime(image.overlay_path)) if image.overlay_path else None
        overlay_html = (
            f'<img src="{overlay}" alt="叠加图"/>' if overlay else '<p class="muted">尚未生成叠加图</p>'
        )
        rows = []
        for damage in damage_by_image.get(image.id, []):
            item = items_by_damage.get(damage.id)
            rows.append(
                "<tr>"
                f"<td>{_e(DAMAGE_LABELS.get(damage.class_name, damage.class_name))}</td>"
                f"<td>{damage.confidence:.2%}</td>"
                f"<td>{_e(item.part_name if item else damage.part_name or '未确认')}</td>"
                f"<td>{_e(SEVERITY_LABELS.get(item.severity_band if item else damage.severity_band or '', '-'))}</td>"
                f"<td>{_e(ACTION_LABELS.get(item.action if item else damage.action or '', '-'))}</td>"
                f"<td>{_e(item.method if item else damage.method or '-')}</td>"
                f"<td class=\"num\">{('%.2f' % item.subtotal) if item else '-'}</td>"
                "</tr>"
            )
        image_model = image.model_name or model_name
        image_blocks.append(
            f"""
            <section class="image-block">
              <h3>图片：{_e(image.original_name)}（{image.width}×{image.height}，推理模型：{_e(image_model)}）</h3>
              <div class="images">
                <figure><img src="{original}" alt="原图"/><figcaption>原图</figcaption></figure>
                <figure>{overlay_html}<figcaption>掩膜叠加</figcaption></figure>
              </div>
              <table>
                <thead><tr><th>损伤类别</th><th>置信度</th><th>受损部件</th><th>严重度</th><th>维修动作</th><th>方式</th><th>小计（元）</th></tr></thead>
                <tbody>{''.join(rows) or '<tr><td colspan="7">本图无损伤实例</td></tr>'}</tbody>
              </table>
            </section>
            """
        )

    item_rows = []
    for item in quote.items:
        item_rows.append(
            "<tr>"
            f"<td>{_e(item.part_name)}</td>"
            f"<td>{_e(ACTION_LABELS.get(item.action, item.action))}</td>"
            f"<td>{_e(item.method)}</td>"
            f"<td>{_e(SEVERITY_LABELS.get(item.severity_band, item.severity_band))}</td>"
            f"<td class=\"num\">{item.part_price:.2f}</td>"
            f"<td class=\"num\">{item.material_cost:.2f}</td>"
            f"<td class=\"num\">{item.standard_hours:.2f}</td>"
            f"<td class=\"num\">{item.labor_rate:.2f}</td>"
            f"<td class=\"num\">{item.labor_amount:.2f}</td>"
            f"<td class=\"num\">{item.subtotal:.2f}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>定损报告 {_e(report_no)}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: "Microsoft YaHei", "SimSun", sans-serif; color: #111; font-size: 11pt; line-height: 1.6; }}
  h1 {{ font-size: 20pt; text-align: center; margin: 0 0 6px; }}
  h2 {{ font-size: 14pt; border-bottom: 1px solid #000; padding-bottom: 4px; margin-top: 22px; }}
  h3 {{ font-size: 11.5pt; margin: 14px 0 8px; }}
  .meta {{ text-align: center; color: #444; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 14px; font-size: 10pt; }}
  th, td {{ border: 1px solid #000; padding: 5px 6px; vertical-align: top; }}
  th {{ background: #efefef; text-align: left; }}
  td.num {{ text-align: right; white-space: nowrap; }}
  .summary td {{ border: none; padding: 2px 8px 2px 0; }}
  .images {{ display: flex; gap: 12px; }}
  .images figure {{ flex: 1; margin: 0; text-align: center; }}
  .images img {{ width: 100%; border: 1px solid #999; }}
  figcaption {{ font-size: 9pt; color: #444; margin-top: 4px; }}
  .totals {{ width: 60%; margin-left: auto; }}
  .totals td {{ border: 1px solid #000; }}
  .muted {{ color: #666; }}
  .notice {{ font-size: 10pt; color: #333; }}
  .sign {{ margin-top: 26px; display: flex; justify-content: space-between; }}
  .avoid-break {{ page-break-inside: avoid; }}
</style>
</head>
<body>
  <h1>车辆损伤定损报告</h1>
  <div class="meta">报告编号：{_e(report_no)}　生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}</div>

  <h2>一、案件摘要</h2>
  <table class="summary">
    <tr><td>案件编号</td><td>{_e(case.case_no)}</td><td>处理状态</td><td>{_e(case.status)}</td></tr>
    <tr><td>车辆</td><td>{_e(case.brand)} {_e(case.series)} {_e(case.vehicle_year or '')} {_e(case.trim)}</td><td>地区</td><td>{_e(case.region_name)}（{_e(case.region_code)}）</td></tr>
    <tr><td>办案人</td><td>{_e(case.created_by_name)}</td><td>模型版本</td><td>{_e(model_name)}</td></tr>
    <tr><td>报价编号</td><td>{_e(quote.quote_no)}</td><td>报价时间</td><td>{quote.created_at.strftime('%Y-%m-%d %H:%M:%S') if quote.created_at else ''}</td></tr>
    <tr><td>规则版本</td><td>{_e(quote.pricing_rule_version)}</td><td>公式版本</td><td>{_e(quote.formula_version)}</td></tr>
  </table>

  <h2>二、损伤识别与人工确认</h2>
  {''.join(image_blocks) or '<p class="muted">本案未上传图片。</p>'}

  <h2>三、费用明细</h2>
  <p class="notice">计价公式：{_e(FORMULA_TEXT)}。更换类动作计入配件费；维修/喷漆类动作不计配件费，仅计材料费与工时费。</p>
  <table>
    <thead>
      <tr><th>部件</th><th>动作</th><th>方式</th><th>严重度</th><th>配件费</th><th>材料费</th><th>标准工时</th><th>工时单价</th><th>工时费</th><th>小计</th></tr>
    </thead>
    <tbody>{''.join(item_rows) or '<tr><td colspan="10">无报价明细</td></tr>'}</tbody>
  </table>

  <table class="totals">
    <tr><td>费用下限</td><td class="num">{quote.total_low:.2f} 元</td></tr>
    <tr><td>参考金额</td><td class="num"><strong>{quote.total_mid:.2f} 元</strong></td></tr>
    <tr><td>费用上限</td><td class="num">{quote.total_high:.2f} 元</td></tr>
  </table>

  <h2>四、说明与确认</h2>
  <p class="notice">
    1. 本报告为辅助定损结果，损伤识别由 {_e(model_name)} 模型完成，部件、严重度与维修动作经人工确认后进入规则报价。<br/>
    2. 费用区间依据配件价格低/中/高位与材料、工时浮动计算，不代表任何实际结算金额。<br/>
    3. 报价快照已固化规则版本与价格版本，主数据后续变更不影响本报告金额。<br/>
    4. 结构性裂纹、需复核实例须由审核人员复核后使用。
  </p>
  <div class="sign">
    <span>定损员：{_e(quote.created_by_name)}</span>
    <span>审核员：{_e(quote.confirmed_by or '待审核')}</span>
    <span>生成时间：{generated_at.strftime('%Y-%m-%d %H:%M')}</span>
  </div>
</body>
</html>"""
