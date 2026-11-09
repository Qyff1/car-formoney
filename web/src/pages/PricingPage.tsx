import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  Catalog,
  LaborRow,
  MaterialRow,
  PartRow,
  RegionRow,
  RuleRow,
  ThresholdRow,
} from "../types";

type EditType = "parts" | "labor" | "materials" | "regions" | "rules";
interface Editing {
  type: EditType;
  row: PartRow | LaborRow | MaterialRow | RegionRow | RuleRow;
}

const ENDPOINTS: Record<EditType, string> = {
  parts: "/api/pricing/parts",
  labor: "/api/pricing/labor",
  materials: "/api/pricing/materials",
  regions: "/api/pricing/regions",
  rules: "/api/pricing/rules",
};

const TITLES: Record<EditType, string> = {
  parts: "调整配件价格",
  labor: "调整标准工时",
  materials: "调整材料费",
  regions: "调整地区工时单价",
  rules: "调整定价规则",
};

export default function PricingPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [saving, setSaving] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<Editing | null>(null);
  const [historyRows, setHistoryRows] = useState<Record<string, any>[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [partModel, setPartModel] = useState("all");
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      setCatalog(await api.get<Catalog>("/api/pricing/catalog"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openEdit = (type: EditType, row: Editing["row"]) => {
    setEditing({ type, row });
    form.resetFields();
    form.setFieldsValue(row as any);
  };

  const submit = async () => {
    if (!editing) return;
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.put(`${ENDPOINTS[editing.type]}/${editing.row.id}`, values);
      message.success("已生成新版本，历史报价快照不受影响");
      setEditing(null);
      await load();
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const editButton = (type: EditType, row: Editing["row"]) => (
    <Space size={0}>
      {isAdmin ? (
        <Button size="small" onClick={() => openEdit(type, row)}>
          调整
        </Button>
      ) : (
        <span className="muted">只读</span>
      )}
      <Button size="small" type="link" onClick={() => openHistory(type, row)}>
        历史
      </Button>
    </Space>
  );

  const openHistory = async (type: EditType, row: Editing["row"]) => {
    setHistoryTarget({ type, row });
    setHistoryLoading(true);
    try {
      setHistoryRows(await api.get<Record<string, any>[]>(`/api/pricing/${type}/${row.id}/history`));
    } catch (error) {
      message.error((error as Error).message);
      setHistoryRows([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const summarizeHistory = (type: EditType, row: Record<string, any>) => {
    switch (type) {
      case "parts":
        return `${row.part_name} · 低 ${row.price_low} / 中 ${row.list_price} / 高 ${row.price_high}`;
      case "labor":
        return `${row.action} / ${row.severity_band} · ${row.standard_hours} 小时`;
      case "materials":
        return `${row.action} / ${row.severity_band} · ${row.material_cost} 元`;
      case "regions":
        return `${row.region_name} · ${row.labor_rate} 元/工时 × ${row.coefficient}`;
      default:
        return `${row.action} · 优先级 ${row.priority} · ${row.method || "-"}`;
    }
  };

  const rollback = async (targetId: number) => {
    if (!historyTarget) return;
    setRollingBack(true);
    try {
      await api.post(
        `/api/pricing/${historyTarget.type}/${historyTarget.row.id}/rollback?target_id=${targetId}`,
      );
      message.success("已按所选历史版本生成新版本");
      await load();
      await openHistory(historyTarget.type, historyTarget.row);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setRollingBack(false);
    }
  };

  const vehicleModels = (catalog?.vehicle_models || []) as Array<{
    id: number;
    brand: string;
    series: string;
  }>;
  const vehicleLabel = (id: number | null) => {
    if (id === null) return "通用兜底";
    const row = vehicleModels.find((item) => item.id === id);
    return row ? `${row.brand} ${row.series}` : `车型 #${id}`;
  };
  const partsData = (catalog?.parts || []).filter((row) => {
    if (partModel === "all") return true;
    if (partModel === "generic") return row.vehicle_model_id === null;
    return row.vehicle_model_id === Number(partModel);
  });

  const partColumns: ColumnsType<PartRow> = [
    { title: "部件", dataIndex: "part_name", width: 120 },
    {
      title: "车型",
      key: "vehicle",
      width: 150,
      render: (_, row) => vehicleLabel(row.vehicle_model_id),
    },
    {
      title: "年款",
      dataIndex: "vehicle_year",
      width: 80,
      align: "center",
      render: (v: number | null) => v ?? "通用",
    },
    { title: "编码", dataIndex: "part_code", width: 130 },
    { title: "类别", dataIndex: "category", width: 80 },
    { title: "可更换", dataIndex: "replaceable", width: 80, render: (v) => (v ? "是" : "否") },
    { title: "低价", dataIndex: "price_low", align: "right", render: (v: number) => v.toFixed(2) },
    { title: "中价", dataIndex: "list_price", align: "right", render: (v: number) => v.toFixed(2) },
    { title: "高价", dataIndex: "price_high", align: "right", render: (v: number) => v.toFixed(2) },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
    { title: "操作", key: "op", width: 150, render: (_, row) => editButton("parts", row) },
  ];

  const laborColumns: ColumnsType<LaborRow> = [
    { title: "部件", dataIndex: "part_code", render: (v: string | null) => v || <Tag>通用</Tag> },
    { title: "损伤类型", dataIndex: "damage_type", render: (v: string | null) => v || "不限" },
    { title: "动作", dataIndex: "action" },
    { title: "严重度", dataIndex: "severity_band" },
    { title: "标准工时（小时）", dataIndex: "standard_hours", align: "right" },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
    { title: "操作", key: "op", width: 150, render: (_, row) => editButton("labor", row) },
  ];

  const materialColumns: ColumnsType<MaterialRow> = [
    { title: "部件", dataIndex: "part_code", render: (v: string | null) => v || <Tag>通用</Tag> },
    { title: "动作", dataIndex: "action" },
    { title: "严重度", dataIndex: "severity_band" },
    { title: "材料费（元）", dataIndex: "material_cost", align: "right" },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
    { title: "操作", key: "op", width: 150, render: (_, row) => editButton("materials", row) },
  ];

  const regionColumns: ColumnsType<RegionRow> = [
    { title: "地区编码", dataIndex: "region_code", width: 110 },
    { title: "地区", dataIndex: "region_name", width: 120 },
    { title: "工时单价（元）", dataIndex: "labor_rate", align: "right" },
    { title: "地区系数", dataIndex: "coefficient", align: "right" },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
    { title: "操作", key: "op", width: 150, render: (_, row) => editButton("regions", row) },
  ];

  const ruleColumns: ColumnsType<RuleRow> = [
    { title: "规则编码", dataIndex: "rule_code", width: 170 },
    { title: "损伤类型", dataIndex: "damage_type", width: 110 },
    { title: "优先级", dataIndex: "priority", width: 80, align: "center" },
    {
      title: "面积区间",
      key: "area",
      width: 150,
      render: (_, row) => `${(row.area_ratio_min * 100).toFixed(2)}% ~ ${row.area_ratio_max === null ? "不限" : `${(row.area_ratio_max * 100).toFixed(2)}%`}`,
    },
    { title: "动作", dataIndex: "action", width: 110 },
    { title: "方式", dataIndex: "method" },
    {
      title: "需复核",
      dataIndex: "requires_review",
      width: 80,
      render: (v: boolean) => (v ? <Tag color="orange">是</Tag> : "否"),
    },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
    { title: "操作", key: "op", width: 150, render: (_, row) => editButton("rules", row) },
  ];

  const thresholdColumns: ColumnsType<ThresholdRow> = [
    { title: "损伤类型", dataIndex: "damage_type" },
    { title: "轻微上限（面积占比）", dataIndex: "minor_max", align: "right", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "严重下限（面积占比）", dataIndex: "severe_min", align: "right", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "版本", dataIndex: "version", width: 70, align: "center" },
  ];

  return (
    <div>
      <h2 className="page-title">价格与规则主数据</h2>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div className="muted">
          修改采用版本化写入：原记录标记为历史版本，新记录版本号 +1。报价已保存快照，主数据变更不影响历史报价。
          {!isAdmin && " 当前角色为只读，需系统管理员调整。"}
        </div>
      </Card>

      <Card size="small" loading={loading && !catalog}>
        <Tabs
          items={[
            {
              key: "parts",
              label: "配件价格",
              children: (
                <>
                  <Space style={{ marginBottom: 8 }}>
                    <Select
                      value={partModel}
                      onChange={setPartModel}
                      style={{ width: 220 }}
                      options={[
                        { value: "all", label: "全部车型" },
                        { value: "generic", label: "通用兜底" },
                        ...vehicleModels.map((item) => ({
                          value: String(item.id),
                          label: `${item.brand} ${item.series}`,
                        })),
                      ]}
                    />
                    <span className="muted">
                      共 {partsData.length} 条；同一配件按车型与年款分别定价
                    </span>
                  </Space>
                  <Table
                    rowKey="id"
                    size="small"
                    pagination={{ pageSize: 12 }}
                    columns={partColumns}
                    dataSource={partsData}
                    scroll={{ x: 1100 }}
                  />
                </>
              ),
            },
            {
              key: "labor",
              label: "工时标准",
              children: (
                <Table
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 12 }}
                  columns={laborColumns}
                  dataSource={catalog?.labor || []}
                />
              ),
            },
            {
              key: "materials",
              label: "材料费",
              children: (
                <Table
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 12 }}
                  columns={materialColumns}
                  dataSource={catalog?.materials || []}
                />
              ),
            },
            {
              key: "regions",
              label: "地区费率",
              children: (
                <Table
                  rowKey="id"
                  size="small"
                  pagination={false}
                  columns={regionColumns}
                  dataSource={catalog?.regions || []}
                />
              ),
            },
            {
              key: "rules",
              label: "定价规则",
              children: (
                <Table
                  rowKey="id"
                  size="small"
                  pagination={false}
                  columns={ruleColumns}
                  dataSource={catalog?.rules || []}
                  scroll={{ x: 1080 }}
                />
              ),
            },
            {
              key: "thresholds",
              label: "严重度阈值",
              children: (
                <Table
                  rowKey="id"
                  size="small"
                  pagination={false}
                  columns={thresholdColumns}
                  dataSource={catalog?.thresholds || []}
                />
              ),
            },
          ]}
        />
      </Card>

      <Modal
        open={Boolean(editing)}
        title={editing ? TITLES[editing.type] : ""}
        onCancel={() => setEditing(null)}
        onOk={submit}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          {editing?.type === "parts" && (
            <>
              <Form.Item name="price_low" label="配件低价" rules={[{ required: true }]}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="list_price" label="配件中价" rules={[{ required: true }]}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="price_high" label="配件高价" rules={[{ required: true }]}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
            </>
          )}
          {editing?.type === "labor" && (
            <Form.Item name="standard_hours" label="标准工时（小时）" rules={[{ required: true }]}>
              <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          )}
          {editing?.type === "materials" && (
            <Form.Item name="material_cost" label="材料费（元）" rules={[{ required: true }]}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          )}
          {editing?.type === "regions" && (
            <>
              <Form.Item name="labor_rate" label="工时单价（元/工时）" rules={[{ required: true }]}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="coefficient" label="地区系数" rules={[{ required: true }]}>
                <InputNumber min={0.1} max={5} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
            </>
          )}
          {editing?.type === "rules" && (
            <>
              <Form.Item name="priority" label="优先级" rules={[{ required: true }]}>
                <InputNumber min={0} max={1000} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="area_ratio_min" label="面积下限（比例，如 0.005）" rules={[{ required: true }]}>
                <InputNumber min={0} max={1} step={0.001} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="area_ratio_max" label="面积上限（留空表示不限）">
                <InputNumber min={0} max={1} step={0.001} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="action" label="维修动作" rules={[{ required: true }]}>
                <Select
                  options={Object.entries(catalog?.labels.actions || {}).map(([value, label]) => ({
                    value,
                    label,
                  }))}
                />
              </Form.Item>
              <Form.Item name="method" label="维修方式">
                <Input />
              </Form.Item>
              <Form.Item name="requires_review" label="需要复核" valuePropName="checked">
                <Switch />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      <Modal
        open={Boolean(historyTarget)}
        title={historyTarget ? `${TITLES[historyTarget.type]} · 历史版本` : ""}
        onCancel={() => setHistoryTarget(null)}
        footer={null}
        width={760}
        destroyOnClose
      >
        <div className="muted" style={{ marginBottom: 8 }}>
          回滚不会删除历史：系统按所选版本的值生成一条新版本并设为当前。
        </div>
        <Table
          rowKey="id"
          size="small"
          loading={historyLoading}
          pagination={false}
          dataSource={historyRows}
          columns={[
            { title: "版本", dataIndex: "version", width: 70 },
            {
              title: "状态",
              key: "state",
              width: 80,
              render: (_, row) =>
                row.is_current ? <Tag color="green">当前</Tag> : <Tag>历史</Tag>,
            },
            {
              title: "内容",
              key: "summary",
              render: (_, row) => (historyTarget ? summarizeHistory(historyTarget.type, row) : "-"),
            },
            {
              title: "操作",
              key: "op",
              width: 100,
              render: (_, row) =>
                row.is_current || !isAdmin ? (
                  <span className="muted">-</span>
                ) : (
                  <Popconfirm
                    title={`按 v${row.version} 生成新版本？`}
                    onConfirm={() => rollback(row.id)}
                  >
                    <Button size="small" loading={rollingBack}>
                      回滚
                    </Button>
                  </Popconfirm>
                ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
