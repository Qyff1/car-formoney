import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Popconfirm,
  Select,
  Slider,
  Space,
  Tag,
  message,
} from "antd";
import { ReloadOutlined, FileTextOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { CaseDetail, Catalog, Damage, Quote, QuotePreview, Report } from "../types";

const CLASS_COLORS: Record<string, string> = {
  dent: "#fa8c16",
  scratch: "#13c2c2",
  crack: "#f5222d",
  "glass shatter": "#722ed1",
  "lamp broken": "#2f54eb",
  "tire flat": "#52c41a",
};

interface EditState {
  part_code: string;
  severity_band: string;
  action: string;
  method: string;
  note: string;
}

export default function WorkbenchPage() {
  const { id } = useParams();
  const caseId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const canConfirm = ["adjuster", "admin"].includes(user?.role || "");

  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [damages, setDamages] = useState<Damage[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [preview, setPreview] = useState<QuotePreview | null>(null);
  const [edits, setEdits] = useState<Record<number, EditState>>({});
  const [selected, setSelected] = useState<number | null>(null);
  const [activeImageId, setActiveImageId] = useState<number | null>(null);
  const [showMask, setShowMask] = useState(true);
  const [opacity, setOpacity] = useState(0.35);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [quoting, setQuoting] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);

  const loadPreview = async () => {
    if (!canConfirm) return;
    try {
      setPreview(await api.post<QuotePreview>("/api/quotes/preview", { case_id: caseId }));
    } catch {
      setPreview(null);
    }
  };

  const load = async () => {
    setLoading(true);
    try {
      const [caseData, damageData, catalogData, reportData] = await Promise.all([
        api.get<CaseDetail>(`/api/cases/${caseId}`),
        api.get<Damage[]>(`/api/cases/${caseId}/damages`),
        api.get<Catalog>("/api/pricing/catalog"),
        api.get<Report[]>(`/api/cases/${caseId}/reports`),
      ]);
      setDetail(caseData);
      setDamages(damageData);
      setCatalog(catalogData);
      setReports(reportData);
      setActiveImageId((prev) => prev ?? caseData.images[0]?.id ?? null);
      const next: Record<number, EditState> = {};
      damageData.forEach((damage) => {
        next[damage.id] = {
          part_code: damage.part_code || "",
          severity_band: damage.severity_band || damage.suggestion?.severity_band || "medium",
          action: damage.action || damage.suggestion?.action || "repair",
          method: damage.method || damage.suggestion?.method || "",
          note: damage.note || "",
        };
      });
      setEdits(next);
      await loadPreview();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  const partOptions = useMemo(() => {
    if (!catalog) return [];
    const seen = new Set<string>();
    return catalog.parts
      .filter((part) => {
        if (seen.has(part.part_code)) return false;
        seen.add(part.part_code);
        return true;
      })
      .map((part) => ({
        value: part.part_code,
        label: `${part.part_name}（${part.category}）`,
      }));
  }, [catalog]);

  const activeImage = detail?.images.find((image) => image.id === activeImageId) || null;
  const visibleDamages = damages.filter((damage) => damage.image_id === activeImageId);

  const updateEdit = (damageId: number, patch: Partial<EditState>) => {
    setEdits((prev) => ({ ...prev, [damageId]: { ...prev[damageId], ...patch } }));
  };

  const saveDamage = async (damage: Damage) => {
    const edit = edits[damage.id];
    if (!edit) return;
    if (!edit.part_code) {
      message.warning("请先选择受损部件");
      return;
    }
    setSavingId(damage.id);
    try {
      const updated = await api.put<Damage>(`/api/damages/${damage.id}`, {
        part_code: edit.part_code,
        severity_band: edit.severity_band,
        action: edit.action,
        method: edit.method || undefined,
        note: edit.note || undefined,
        confirmed: true,
      });
      setDamages((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEdits((prev) => ({
        ...prev,
        [updated.id]: {
          part_code: updated.part_code || "",
          severity_band: updated.severity_band || "medium",
          action: updated.action || "repair",
          method: updated.method || "",
          note: updated.note || "",
        },
      }));
      message.success("已保存并确认");
      await loadPreview();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  const reanalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await api.post<{ damage_count: number }>("/api/analyses", { case_id: caseId });
      message.success(`重新分析完成，识别到 ${result.damage_count} 个损伤实例`);
      setSelected(null);
      await load();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const createQuote = async () => {
    setQuoting(true);
    try {
      const quote = await api.post<Quote>("/api/quotes", { case_id: caseId });
      message.success("报价已生成");
      navigate(`/quotes/${quote.id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setQuoting(false);
    }
  };

  const confirmedCount = damages.filter((damage) => damage.confirmed).length;

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }} loading={loading && !detail}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <Space size={16} wrap>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{detail?.case_no || "案件"}</span>
            <Tag color="blue">{detail?.status_label}</Tag>
            <span>
              {detail?.brand} {detail?.series} {detail?.vehicle_year || ""} {detail?.trim}
            </span>
            <span className="muted">
              {detail?.region_name} · 办案人 {detail?.created_by_name}
            </span>
          </Space>
          <Space wrap>
            <Popconfirm title="重新分析会覆盖当前损伤实例与人工确认，是否继续？" onConfirm={reanalyze}>
              <Button icon={<ReloadOutlined />} loading={analyzing} disabled={!detail?.images.length}>
                重新分析
              </Button>
            </Popconfirm>
            {reports.length > 0 && (
              <Button icon={<FileTextOutlined />} onClick={() => navigate(`/reports/${caseId}`)}>
                查看报告
              </Button>
            )}
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={quoting}
              onClick={createQuote}
              disabled={!damages.length || !canConfirm}
              title={canConfirm ? undefined : "仅查勘定损员 / 管理员可生成报价"}
            >
              生成报价
            </Button>
          </Space>
        </div>
      </Card>

      {!canConfirm && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="当前角色为审核员：可查看案件与报价并确认报价；损伤确认与报价生成由查勘定损员完成。"
        />
      )}

      <div className="case-layout">
        <div className="case-left">
          <Card
            size="small"
            title={activeImage ? `损伤叠加：${activeImage.original_name}` : "损伤叠加"}
            extra={
              <Space size={8}>
                <span className="muted">掩膜</span>
                <Slider
                  style={{ width: 110 }}
                  min={0}
                  max={1}
                  step={0.05}
                  value={opacity}
                  onChange={setOpacity}
                  disabled={!showMask}
                />
                <Button size="small" onClick={() => setShowMask((v) => !v)}>
                  {showMask ? "隐藏" : "显示"}
                </Button>
              </Space>
            }
          >
            {activeImage ? (
              <div className="canvas-wrap">
                <img src={activeImage.url} alt={activeImage.original_name} />
                {showMask && (
                  <svg viewBox={`0 0 ${activeImage.width} ${activeImage.height}`} preserveAspectRatio="none">
                    {visibleDamages.map((damage) =>
                      damage.polygons.map((polygon, index) => (
                        <polygon
                          key={`${damage.id}-${index}`}
                          points={polygon.map((point) => point.join(",")).join(" ")}
                          fill={CLASS_COLORS[damage.class_name] || "#1677ff"}
                          fillOpacity={selected === damage.id ? Math.min(opacity + 0.25, 0.9) : opacity}
                          stroke={selected === damage.id ? "#ffffff" : CLASS_COLORS[damage.class_name] || "#1677ff"}
                          strokeWidth={selected === damage.id ? 3 : 1.5}
                          style={{ cursor: "pointer" }}
                          onClick={() => setSelected(damage.id)}
                        />
                      )),
                    )}
                  </svg>
                )}
              </div>
            ) : (
              <Alert type="info" message="本案尚未上传图片或尚未分析" />
            )}
            {detail && detail.images.length > 1 && (
              <div className="thumb-row">
                {detail.images.map((image) => (
                  <img
                    key={image.id}
                    src={image.url}
                    alt={image.original_name}
                    className={`thumb${image.id === activeImageId ? " active" : ""}`}
                    onClick={() => setActiveImageId(image.id)}
                  />
                ))}
              </div>
            )}
          </Card>

          <Card size="small" style={{ marginTop: 16 }} title="案件信息">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="案件编号">{detail?.case_no}</Descriptions.Item>
              <Descriptions.Item label="状态">{detail?.status_label}</Descriptions.Item>
              <Descriptions.Item label="车辆">
                {detail?.brand} {detail?.series} {detail?.vehicle_year || ""}
              </Descriptions.Item>
              <Descriptions.Item label="地区">{detail?.region_name}</Descriptions.Item>
              <Descriptions.Item label="图片数">{detail?.image_count}</Descriptions.Item>
              <Descriptions.Item label="损伤实例">{damages.length}</Descriptions.Item>
              <Descriptions.Item label="已确认">{confirmedCount}</Descriptions.Item>
              <Descriptions.Item label="最新报价">
                {detail?.latest_quote ? `${detail.latest_quote.total_mid.toFixed(2)} 元` : "未报价"}
              </Descriptions.Item>
            </Descriptions>
            {detail?.latest_quote && (
              <Button size="small" onClick={() => navigate(`/quotes/${detail.latest_quote!.id}`)}>
                查看最新报价
              </Button>
            )}
          </Card>

          {canConfirm && detail && !["quoted", "reported"].includes(detail.status) && (
            <Card
              size="small"
              style={{ marginTop: 16 }}
              title="报价预估（实时）"
              extra={<span className="muted">仅统计已确认损伤</span>}
            >
              {preview && preview.items.length > 0 ? (
                <>
                  <Descriptions size="small" column={3}>
                    <Descriptions.Item label="下限">{preview.total_low.toFixed(2)}</Descriptions.Item>
                    <Descriptions.Item label="参考">
                      <strong>{preview.total_mid.toFixed(2)}</strong>
                    </Descriptions.Item>
                    <Descriptions.Item label="上限">{preview.total_high.toFixed(2)}</Descriptions.Item>
                  </Descriptions>
                  <div style={{ marginTop: 4 }}>
                    {preview.items.map((item) => (
                      <div
                        key={item.damage_id}
                        style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 13 }}
                      >
                        <span>
                          {item.part_name} · {item.action_label}
                          {item.method && item.method !== item.action_label ? `（${item.method}）` : ""} ·{" "}
                          {item.severity_label}
                        </span>
                        <span>{item.subtotal.toFixed(2)} 元</span>
                      </div>
                    ))}
                  </div>
                  {preview.pending_count > 0 && (
                    <Alert
                      type="warning"
                      showIcon
                      style={{ marginTop: 8 }}
                      message={`还有 ${preview.pending_count} 条损伤未确认，未计入预估`}
                    />
                  )}
                </>
              ) : (
                <div className="muted">
                  {preview && preview.pending_count > 0
                    ? `还有 ${preview.pending_count} 条损伤未确认，完成确认后自动试算`
                    : "完成损伤确认后自动试算"}
                </div>
              )}
            </Card>
          )}
        </div>

        <div className="case-right">
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            损伤实例（{visibleDamages.length}）
          </div>
          {visibleDamages.length === 0 && <Alert type="info" message="当前图片没有识别到损伤实例" />}
          {visibleDamages.map((damage) => {
            const edit = edits[damage.id];
            return (
              <Card
                key={damage.id}
                size="small"
                className={`damage-card${selected === damage.id ? " selected" : ""}`}
                style={{ borderLeftColor: CLASS_COLORS[damage.class_name] || "#1677ff", cursor: "pointer" }}
                onClick={() => setSelected(damage.id)}
                title={
                  <Space size={8} wrap>
                    <Tag color={CLASS_COLORS[damage.class_name] || "blue"}>{damage.class_label}</Tag>
                    <span className="muted">置信度 {(damage.confidence * 100).toFixed(1)}%</span>
                    <span className="muted">面积占比 {(damage.mask_area_ratio * 100).toFixed(2)}%</span>
                    {damage.needs_review && <Tag color="orange">待复核</Tag>}
                    {damage.confirmed && <Tag color="green">已确认</Tag>}
                  </Space>
                }
              >
                <Space direction="vertical" style={{ width: "100%" }} size={8}>
                  <Select
                    style={{ width: "100%" }}
                    placeholder="选择受损部件"
                    showSearch
                    optionFilterProp="label"
                    value={edit?.part_code || undefined}
                    options={partOptions}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(value) => updateEdit(damage.id, { part_code: value })}
                  />
                  <Space.Compact style={{ width: "100%" }}>
                    <Select
                      style={{ width: "50%" }}
                      value={edit?.severity_band}
                      options={Object.entries(catalog?.labels.severities || {}).map(([value, label]) => ({
                        value,
                        label,
                      }))}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(value) => updateEdit(damage.id, { severity_band: value })}
                    />
                    <Select
                      style={{ width: "50%" }}
                      value={edit?.action}
                      options={Object.entries(catalog?.labels.actions || {}).map(([value, label]) => ({
                        value,
                        label,
                      }))}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(value) => updateEdit(damage.id, { action: value })}
                    />
                  </Space.Compact>
                  <Input
                    placeholder="维修方式（如 局部补漆）"
                    value={edit?.method}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => updateEdit(damage.id, { method: e.target.value })}
                  />
                  <Input
                    placeholder="备注 / 人工修改原因"
                    value={edit?.note}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => updateEdit(damage.id, { note: e.target.value })}
                  />
                  {damage.suggestion && (
                    <div className="muted">
                      规则建议：{damage.suggestion.severity_label} / {damage.suggestion.action_label || "人工判断"}
                      {damage.suggestion.method ? `（${damage.suggestion.method}）` : ""}
                      {damage.suggestion.requires_review ? " · 需复核" : ""}
                    </div>
                  )}
                  <Button
                    type="primary"
                    size="small"
                    loading={savingId === damage.id}
                    disabled={!canConfirm}
                    title={canConfirm ? undefined : "仅查勘定损员 / 管理员可确认"}
                    onClick={(e) => {
                      e.stopPropagation();
                      saveDamage(damage);
                    }}
                  >
                    {damage.confirmed ? "更新确认" : "保存并确认"}
                  </Button>
                </Space>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
