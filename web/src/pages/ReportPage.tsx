import { Button, Card, Empty, Select, Space, message } from "antd";
import { FilePdfOutlined, ReloadOutlined } from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { CaseSummary, Report } from "../types";

export default function ReportPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [caseInfo, setCaseInfo] = useState<CaseSummary | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const load = async () => {
    try {
      const [caseData, reportData] = await Promise.all([
        api.get<CaseSummary>(`/api/cases/${caseId}`),
        api.get<Report[]>(`/api/cases/${caseId}/reports`),
      ]);
      setCaseInfo(caseData);
      setReports(reportData);
      setSelectedId((prev) => prev ?? reportData[0]?.id ?? null);
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  const current = reports.find((report) => report.id === selectedId);
  const url = current?.file_url || current?.html_url || "";

  const printReport = () => {
    const frame = frameRef.current;
    if (!frame?.contentWindow) {
      message.warning("报告尚未加载完成");
      return;
    }
    frame.contentWindow.focus();
    frame.contentWindow.print();
  };

  return (
    <div>
      <h2 className="page-title">定损报告</h2>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>
            案件：<a onClick={() => navigate(`/cases/${caseInfo?.id}`)}>{caseInfo?.case_no}</a>
          </span>
          <span className="muted">
            {caseInfo?.brand} {caseInfo?.series} {caseInfo?.vehicle_year || ""}
          </span>
          <Select
            style={{ width: 240 }}
            placeholder="选择报告"
            value={selectedId || undefined}
            onChange={setSelectedId}
            options={reports.map((report) => ({
              value: report.id,
              label: `${report.report_no}（${report.generated_at.replace("T", " ").slice(0, 16)}）`,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button
            icon={<FilePdfOutlined />}
            type="primary"
            onClick={printReport}
            disabled={!current}
          >
            打印 / 导出 PDF
          </Button>
          {current && (
            <Button onClick={() => window.open(url, "_blank")} disabled={!url}>
              新窗口打开
            </Button>
          )}
        </Space>
      </Card>

      <Card size="small" bodyStyle={{ padding: 12 }}>
        {current ? (
          <iframe ref={frameRef} className="report-frame" src={url} title={current.report_no} />
        ) : (
          <Empty description="本案尚未生成报告，请先在报价页确认报价后生成" />
        )}
      </Card>
    </div>
  );
}
