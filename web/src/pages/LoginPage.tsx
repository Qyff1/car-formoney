import { Button, Form, Input, Table, Typography, message } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const DEMO_ACCOUNTS = [
  { username: "周显鑫0", role: "查勘定损员", desc: "建案上传、发起分析、确认损伤、生成报价与报告" },
  { username: "周显鑫1", role: "审核员", desc: "复核并确认报价、查看报告" },
  { username: "周显鑫2", role: "系统管理员", desc: "主数据维护、模型切换、审计" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success("登录成功");
      navigate("/");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-title">车辆损伤智能定损系统</div>
        <div className="login-sub">图像分析 · 人工确认 · 规则定价</div>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ username: "周显鑫0", password: "Cardd@2026" }}
          onFinish={onFinish}
        >
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading}>
            登录
          </Button>
        </Form>
        <div style={{ marginTop: 22 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            演示账号（初始密码均为 Cardd@2026，点击行可快速填入）
          </Typography.Text>
          <Table
            size="small"
            style={{ marginTop: 8 }}
            pagination={false}
            dataSource={DEMO_ACCOUNTS}
            rowKey="username"
            onRow={(record) => ({
              onClick: () => form.setFieldsValue({ username: record.username, password: "Cardd@2026" }),
              style: { cursor: "pointer" },
            })}
            columns={[
              { title: "账号", dataIndex: "username", width: 96 },
              { title: "角色", dataIndex: "role", width: 88 },
              { title: "可用操作", dataIndex: "desc" },
            ]}
          />
        </div>
      </div>
    </div>
  );
}
