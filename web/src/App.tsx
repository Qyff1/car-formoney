import { Navigate, Outlet, Route, Routes, BrowserRouter, useLocation } from "react-router-dom";
import { Spin } from "antd";
import { useAuth } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import LoginPage from "./pages/LoginPage";
import CaseListPage from "./pages/CaseListPage";
import CaseNewPage from "./pages/CaseNewPage";
import WorkbenchPage from "./pages/WorkbenchPage";
import QuotePage from "./pages/QuotePage";
import ReportPage from "./pages/ReportPage";
import PricingPage from "./pages/PricingPage";
import ModelPage from "./pages/ModelPage";
import AuditPage from "./pages/AuditPage";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" tip="正在校验登录状态" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function LoginGate() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <LoginPage />;
}

function ScrollTopOnNavigate() {
  const location = useLocation();
  if (typeof window !== "undefined") window.scrollTo(0, 0);
  return <span key={location.pathname} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollTopOnNavigate />
      <Routes>
        <Route path="/login" element={<LoginGate />} />
        <Route element={<Protected />}>
          <Route element={<AppLayout />}>
            <Route index element={<CaseListPage />} />
            <Route path="cases/new" element={<CaseNewPage />} />
            <Route path="cases/:id" element={<WorkbenchPage />} />
            <Route path="quotes/:id" element={<QuotePage />} />
            <Route path="reports/:caseId" element={<ReportPage />} />
            <Route path="pricing" element={<PricingPage />} />
            <Route path="models" element={<ModelPage />} />
            <Route path="audit" element={<AuditPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
