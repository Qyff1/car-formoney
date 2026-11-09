import { Card, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { api } from "../api/client";

interface AuditRow {
  id: number;
  username: string;
  role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  detail: Record<string, unknown>;
  created_at: string;
}

const ROLE_LABELS: Record<string, string> = {
  adjuster: "查勘定损员",
  reviewer: "审核员",
  admin: "系统管理员",
};

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .get<AuditRow[]>("/api/audit-logs?limit=200")
      .then(setRows)
      .catch((error) => message.error((error as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const columns: ColumnsType<AuditRow> = [
    {
      title: "时间",
      dataIndex: "created_at",
      width: 170,
      render: (value: string) => value?.replace("T", " ").slice(0, 19),
    },
    { title: "操作人", dataIndex: "username", width: 110 },
    {
      title: "角色",
      dataIndex: "role",
      width: 100,
      render: (value: string) => <Tag>{ROLE_LABELS[value] || value}</Tag>,
    },
    { title: "动作", dataIndex: "action", width: 150 },
    {
      title: "对象",
      key: "entity",
      width: 180,
      render: (_, row) => `${row.entity_type}#${row.entity_id}`,
    },
    {
      title: "详情",
      dataIndex: "detail",
      render: (value) => (
        <span style={{ fontSize: 12, color: "#555", wordBreak: "break-all" }}>
          {JSON.stringify(value)}
        </span>
      ),
    },
  ];

  return (
    <div>
      <h2 className="page-title">审计日志</h2>
      <Card size="small">
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={{ pageSize: 15 }}
        />
      </Card>
    </div>
  );
}
