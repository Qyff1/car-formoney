import { Alert, Button, Card, Descriptions, Space, Statistic, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { CaseSummary, Quote, QuoteItem, Report } from "../types";

export default function QuotePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const quoteId = Number(id);
  const navigate = useNavigate();
  const canReview = ["reviewer", "admin"].includes(user?.role || "");
  const canHandle = ["adjuster", "admin"].includes(user?.role || "");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [caseInfo, setCaseInfo] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [generating, setGenerating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.get<Quote>(`/api/quotes/${quoteId}`);
      setQuote(data);
      const caseData = await api.get<CaseSummary>(`/api/cases/${data.case_id}`);
      setCaseInfo(caseData);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quoteId]);

  const confirm = async () => {
    setConfirming(true);
    try {
      await api.post(`/api/quotes/${quoteId}/confirm`, {});
      message.success("报价已确认并冻结快照");
      await load();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setConfirming(false);
    }
  };

  const generateReport = async () => {
    if (!quote) return;
    setGenerating(true);
    try {
      const report = await api.post<Report>("/api/reports", {
        case_id: quote.case_id,
        quote_id: quote.id,
      });
      message.success(`报告已生成：${report.report_no}`);
      navigate(`/reports/${quote.case_id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  const columns: ColumnsType<QuoteItem> = [
    { title: "部件", dataIndex: "part_name", width: 110 },
    { title: "动作", dataIndex: "action_label", width: 100 },
    { title: "方式", dataIndex: "method", width: 150 },
    { title: "严重度", dataIndex: "severity_label", width: 80 },
    { title: "配件费", dataIndex: "part_price", width: 88, align: "right", render: (v: number) => v.toFixed(2) },
    { title: "材料费", dataIndex: "material_cost", width: 88, align: "right", render: (v: number) => v.toFixed(2) },
    { title: "标准工时", dataIndex: "standard_hours", width: 90, align: "right", render: (v: number) => v.toFixed(2) },
    {
      title: "工时单价",
      key: "rate",
      width: 100,
      align: "right",
      render: (_, row) => `${row.labor_rate.toFixed(2)} × ${row.labor_coefficient}`,
    },
    { title: "工时费", dataIndex: "labor_amount", width: 96, align: "right", render: (v: number) => v.toFixed(2) },
    {
      title: "小计（元）",
      dataIndex: "subtotal",
      width: 110,
      align: "right",
      render: (v: number) => <strong>{v.toFixed(2)}</strong>,
    },
  ];

  return (
    <div>
      <h2 className="page-title">
        报价单 {quote?.quote_no}
        {quote && (
          <Tag color={quote.status === "confirmed" ? "green" : "gold"} style={{ marginLeft: 12 }}>
            {quote.status === "confirmed" ? "已确认" : "草稿"}
          </Tag>
        )}
      </h2>

      <Card size="small" loading={loading} style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="案件编号">
            {caseInfo ? <a onClick={() => navigate(`/cases/${caseInfo.id}`)}>{caseInfo.case_no}</a> : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="车辆">
            {caseInfo?.brand} {caseInfo?.series} {caseInfo?.vehicle_year || ""}
          </Descriptions.Item>
          <Descriptions.Item label="地区">{quote?.region_name}</Descriptions.Item>
          <Descriptions.Item label="规则版本">{quote?.pricing_rule_version}</Descriptions.Item>
          <Descriptions.Item label="公式版本">{quote?.formula_version}</Descriptions.Item>
          <Descriptions.Item label="地区工时单价">
            {quote ? `${quote.labor_rate.toFixed(2)} 元/工时 × ${quote.labor_coefficient}` : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="制单人">{quote?.created_by_name}</Descriptions.Item>
          <Descriptions.Item label="确认人">{quote?.confirmed_by || "未确认"}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {quote?.created_at?.replace("T", " ").slice(0, 19)}
          </Descriptions.Item>
        </Descriptions>
        {quote?.manual_override_reason && (
          <Alert type="warning" showIcon message={`人工覆盖原因：${quote.manual_override_reason}`} />
        )}
      </Card>

      {quote?.items.some((item) => item.requires_review) && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="本次报价包含需复核的损伤项（结构性裂纹或低置信度实例），请审核员复核后再使用。"
        />
      )}

      <Card size="small" title="费用明细" style={{ marginBottom: 16 }}>
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          columns={columns}
          dataSource={quote?.items || []}
          scroll={{ x: 1050 }}
        />
        <div className="quote-total" style={{ marginTop: 20 }}>
          <Statistic title="费用下限" value={quote?.total_low || 0} precision={2} suffix="元" />
          <Statistic
            title="参考金额"
            value={quote?.total_mid || 0}
            precision={2}
            suffix="元"
            valueStyle={{ color: "#1d4ed8", fontWeight: 700 }}
          />
          <Statistic title="费用上限" value={quote?.total_high || 0} precision={2} suffix="元" />
        </div>
        <div className="muted" style={{ marginTop: 12 }}>
          计价公式：维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价。更换类动作计入配件费；
          维修 / 喷漆类动作不计配件费。配件费按车辆年款逐年定价，并按损伤严重度取低 / 中 / 高位价
          （轻微 / 一般 / 严重），材料费与标准工时同按严重度档取值。
        </div>
      </Card>

      <Space>
        <Button onClick={() => navigate(`/cases/${quote?.case_id}`)}>返回工作台</Button>
        {quote?.status === "draft" &&
          (canReview ? (
            <Button type="primary" loading={confirming} onClick={confirm}>
              确认报价
            </Button>
          ) : (
            <span className="muted">报价确认需由审核员完成</span>
          ))}
        {quote?.status === "confirmed" &&
          (canHandle ? (
            <Button type="primary" loading={generating} onClick={generateReport}>
              生成定损报告
            </Button>
          ) : (
            <span className="muted">报告由查勘定损员生成</span>
          ))}
        {caseInfo?.status === "reported" && (
          <Button onClick={() => navigate(`/reports/${caseInfo.id}`)}>查看报告</Button>
        )}
      </Space>
    </div>
  );
}
