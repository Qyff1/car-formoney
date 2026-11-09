import { Button, Card, DatePicker, Input, Select, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { CaseSummary } from "../types";

const STATUS_COLOR: Record<string, string> = {
  draft: "default",
  analyzing: "processing",
  pending_confirm: "warning",
  quoted: "blue",
  reported: "success",
};

const DAMAGE_OPTIONS = [
  { value: "dent", label: "凹陷" },
  { value: "scratch", label: "刮擦" },
  { value: "crack", label: "裂纹" },
  { value: "glass shatter", label: "玻璃破碎" },
  { value: "lamp broken", label: "车灯破损" },
  { value: "tire flat", label: "轮胎损伤" },
];

export default function CaseListPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<string | undefined>();
  const [damageType, setDamageType] = useState<string | undefined>();
  const [range, setRange] = useState<any>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (keyword) params.set("keyword", keyword);
      if (status) params.set("status", status);
      if (damageType) params.set("damage_type", damageType);
      if (range?.[0]) params.set("date_from", range[0].format("YYYY-MM-DD"));
      if (range?.[1]) params.set("date_to", range[1].format("YYYY-MM-DD"));
      const data = await api.get<CaseSummary[]>(`/api/cases?${params.toString()}`);
      setRows(data);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns: ColumnsType<CaseSummary> = [
    {
      title: "案件编号",
      dataIndex: "case_no",
      width: 150,
      render: (value, row) => <a onClick={() => navigate(`/cases/${row.id}`)}>{value}</a>,
    },
    {
      title: "车辆",
      key: "vehicle",
      render: (_, row) => `${row.brand} ${row.series}${row.vehicle_year ? ` ${row.vehicle_year}` : ""}`,
    },
    { title: "地区", dataIndex: "region_name", width: 100 },
    {
      title: "状态",
      dataIndex: "status",
      width: 96,
      render: (value, row) => <Tag color={STATUS_COLOR[value]}>{row.status_label}</Tag>,
    },
    { title: "图片", dataIndex: "image_count", width: 64, align: "center" },
    { title: "损伤实例", dataIndex: "damage_count", width: 84, align: "center" },
    {
      title: "最新报价",
      key: "quote",
      width: 130,
      render: (_, row) =>
        row.latest_quote ? (
          <a onClick={() => navigate(`/quotes/${row.latest_quote!.id}`)}>
            {row.latest_quote.total_mid.toFixed(2)} 元
          </a>
        ) : (
          <span className="muted">未报价</span>
        ),
    },
    { title: "创建人", dataIndex: "created_by_name", width: 90 },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 160,
      render: (value: string) => value?.replace("T", " ").slice(0, 19),
    },
    {
      title: "操作",
      key: "action",
      width: 150,
      render: (_, row) => (
        <Space>
          <Button size="small" type="primary" ghost onClick={() => navigate(`/cases/${row.id}`)}>
            工作台
          </Button>
          {row.latest_quote && (
            <Button size="small" onClick={() => navigate(`/quotes/${row.latest_quote!.id}`)}>
              报价
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <h2 className="page-title">案件管理</h2>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="案件号 / 品牌 / 车系"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Select
            placeholder="案件状态"
            allowClear
            style={{ width: 130 }}
            value={status}
            onChange={setStatus}
            options={[
              { value: "draft", label: "草稿" },
              { value: "pending_confirm", label: "待确认" },
              { value: "quoted", label: "已报价" },
              { value: "reported", label: "已出报告" },
            ]}
          />
          <Select
            placeholder="损伤类型"
            allowClear
            style={{ width: 140 }}
            value={damageType}
            onChange={setDamageType}
            options={DAMAGE_OPTIONS}
          />
          <DatePicker.RangePicker value={range} onChange={(value) => setRange(value)} />
          <Button type="primary" onClick={load} loading={loading}>
            查询
          </Button>
          <Button onClick={() => navigate("/cases/new")}>新建案件</Button>
        </Space>
      </Card>
      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={rows}
        scroll={{ x: 1180 }}
        pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
      />
    </div>
  );
}
