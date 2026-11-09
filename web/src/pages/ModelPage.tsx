import { Button, Card, Space, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { ModelVersion } from "../types";

export default function ModelPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setRows(await api.get<ModelVersion[]>("/api/model-versions"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const activate = async (row: ModelVersion) => {
    try {
      await api.post(`/api/model-versions/${row.id}/activate`);
      message.success(`已切换线上模型：${row.name}`);
      await load();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const columns: ColumnsType<ModelVersion> = [
    {
      title: "模型版本",
      dataIndex: "name",
      width: 220,
      render: (value, row) => (
        <Space>
          <span>{value}</span>
          {row.is_active && <Tag color="green">线上</Tag>}
        </Space>
      ),
    },
    { title: "权重路径", dataIndex: "weights_path", ellipsis: true },
    {
      title: "Mask mAP50-95",
      key: "mask",
      width: 130,
      align: "right",
      render: (_, row) => row.metrics?.overall_mask_map50_95?.toFixed(4) ?? "-",
    },
    {
      title: "Box mAP50-95",
      key: "box",
      width: 120,
      align: "right",
      render: (_, row) => row.metrics?.overall_box_map50_95?.toFixed(4) ?? "-",
    },
    {
      title: "参数量",
      key: "params",
      width: 110,
      align: "right",
      render: (_, row) =>
        row.metrics?.parameters ? `${(row.metrics.parameters / 1_000_000).toFixed(2)} M` : "-",
    },
    {
      title: "P50 时延",
      key: "latency",
      width: 100,
      align: "right",
      render: (_, row) => (row.metrics?.latency_ms?.p50 ? `${row.metrics.latency_ms.p50} ms` : "-"),
    },
    {
      title: "小目标 AP（crack / scratch）",
      key: "small",
      width: 200,
      render: (_, row) => {
        const ap = row.metrics?.per_class_mask_ap50_95;
        if (!ap) return "-";
        return `${ap.crack?.toFixed(4) ?? "-"} / ${ap.scratch?.toFixed(4) ?? "-"}`;
      },
    },
    {
      title: "训练配置",
      key: "train_config",
      width: 220,
      ellipsis: true,
      render: (_, row) => {
        if (!row.train_config) return "-";
        return Object.entries(row.train_config)
          .map(([key, value]) => `${key}=${String(value)}`)
          .join("；");
      },
    },
    {
      title: "数据集哈希",
      dataIndex: "dataset_hash",
      width: 130,
      ellipsis: true,
      render: (value: string | null) =>
        value ? <span title={value}>{value.slice(0, 12)}</span> : "-",
    },
    {
      title: "操作",
      key: "op",
      width: 110,
      render: (_, row) =>
        row.is_active ? (
          <span className="muted">当前线上</span>
        ) : isAdmin ? (
          <Button size="small" onClick={() => activate(row)}>
            设为线上
          </Button>
        ) : (
          <span className="muted">仅管理员</span>
        ),
    },
  ];

  return (
    <div>
      <h2 className="page-title">模型版本管理</h2>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div className="muted">
          系统预置两个模型版本：基线 YOLOv8s-seg 与 P2 改进版（新增 stride=4 小目标分割头），
          指标均来自 CarDD 测试集同口径评测。管理员点击“设为线上”即可切换推理所用版本，
          切换后新发起的分析任务立即生效。
        </div>
      </Card>
      <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 1280 }} />
    </div>
  );
}
