import { Layout, Menu, Avatar, Button, Tag, Space, Typography } from "antd";
import {
  AuditOutlined,
  CarOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  PlusCircleOutlined,
  RobotOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const { Header, Sider, Content } = Layout;

const ROLE_COLOR: Record<string, string> = {
  adjuster: "blue",
  reviewer: "orange",
  admin: "red",
};

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const canHandle = ["adjuster", "admin"].includes(user?.role || "");

  const items = [
    { key: "/", icon: <CarOutlined />, label: "案件管理" },
    ...(canHandle
      ? [{ key: "/cases/new", icon: <PlusCircleOutlined />, label: "新建案件" }]
      : []),
    { key: "/pricing", icon: <DatabaseOutlined />, label: "价格与规则" },
    { key: "/models", icon: <RobotOutlined />, label: "模型管理" },
    ...(user?.role === "admin"
      ? [{ key: "/audit", icon: <AuditOutlined />, label: "审计日志" }]
      : []),
  ];

  const selected = location.pathname.startsWith("/cases/new")
    ? "/cases/new"
    : location.pathname === "/pricing"
      ? "/pricing"
      : location.pathname === "/models"
        ? "/models"
        : location.pathname === "/audit"
          ? "/audit"
          : "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" width={208} breakpoint="lg" collapsedWidth={64}>
        <div style={{ color: "#fff", padding: "18px 16px", fontWeight: 700, fontSize: 15 }}>
          车辆损伤智能定损
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          }}
        >
          <Typography.Text type="secondary">
            图像分析 → 人工确认 → 规则报价 → 定损报告
          </Typography.Text>
          <Space size={12}>
            <Tag color={ROLE_COLOR[user?.role || ""] || "default"}>{user?.role_label}</Tag>
            <Avatar size="small" icon={<UserOutlined />} />
            <span>{user?.full_name || user?.username}</span>
            <Button
              size="small"
              icon={<LogoutOutlined />}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              退出登录
            </Button>
          </Space>
        </Header>
        <Content style={{ padding: 20 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
