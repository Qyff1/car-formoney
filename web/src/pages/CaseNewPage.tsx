import { Alert, Button, Card, Form, Select, Space, Steps, Upload, message } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd/es/upload/interface";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { CaseImage, CaseSummary, RegionRow } from "../types";

const MAX_IMAGES = 10;

interface VehicleOption {
  id: number;
  code: string;
  brand: string;
  series: string;
  year_from: number;
  year_to: number;
  trim: string;
}

export default function CaseNewPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [vehicles, setVehicles] = useState<VehicleOption[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleOption | null>(null);
  const [caseInfo, setCaseInfo] = useState<CaseSummary | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [images, setImages] = useState<CaseImage[]>([]);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<RegionRow[]>("/api/pricing/regions"),
      api.get<VehicleOption[]>("/api/pricing/vehicle-models"),
    ])
      .then(([regionRows, vehicleRows]) => {
        setRegions(regionRows);
        setVehicles(vehicleRows);
      })
      .catch((error) => message.error((error as Error).message));
  }, []);

  const uploadFor = async (caseId: number) => {
    const files = fileList.map((file) => file.originFileObj as File).filter(Boolean);
    if (!files.length) return;
    if (images.length + files.length > MAX_IMAGES) {
      message.warning(`单个案件最多 ${MAX_IMAGES} 张图片，已上传 ${images.length} 张`);
      return;
    }
    setUploading(true);
    try {
      const data = await api.upload<CaseImage[]>(`/api/cases/${caseId}/images`, files);
      setImages((prev) => [...prev, ...data]);
      setFileList([]);
      message.success(`已上传 ${data.length} 张图片`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const createCase = async (values: Record<string, unknown>) => {
    if (!selectedVehicle) {
      message.warning("请先从车型库选择车辆");
      return;
    }
    if (!values.vehicle_year) {
      message.warning("请选择车辆年款，年款决定配件价格");
      return;
    }
    setCreating(true);
    try {
      const data = await api.post<CaseSummary>("/api/cases", {
        brand: selectedVehicle.brand,
        series: selectedVehicle.series,
        vehicle_year: values.vehicle_year,
        trim: selectedVehicle.trim,
        region_code: values.region_code,
      });
      setCaseInfo(data);
      message.success(`案件已创建：${data.case_no}`);
      if (fileList.length > 0) {
        await uploadFor(data.id);
      }
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const uploadImages = async () => {
    if (!caseInfo) {
      message.warning("请先填写车辆信息并创建案件，创建后会自动上传已选图片");
      return;
    }
    await uploadFor(caseInfo.id);
  };

  const analyze = async () => {
    if (!caseInfo) return;
    setAnalyzing(true);
    try {
      const result = await api.post<{ damage_count: number }>("/api/analyses", {
        case_id: caseInfo.id,
      });
      message.success(`分析完成，识别到 ${result.damage_count} 个损伤实例`);
      navigate(`/cases/${caseInfo.id}`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  const remaining = Math.max(MAX_IMAGES - images.length, 0);

  const yearOptions = useMemo(() => {
    if (!selectedVehicle) return [];
    const options: { value: number; label: string }[] = [];
    for (let year = selectedVehicle.year_to; year >= selectedVehicle.year_from; year -= 1) {
      options.push({ value: year, label: `${year} 款` });
    }
    return options;
  }, [selectedVehicle]);

  return (
    <div style={{ maxWidth: 980 }}>
      <h2 className="page-title">新建案件</h2>
      <Steps
        size="small"
        current={caseInfo ? (images.length ? 2 : 1) : 0}
        items={[{ title: "填写车辆信息" }, { title: "上传损伤图片" }, { title: "发起损伤分析" }]}
        style={{ marginBottom: 20 }}
      />

      <Card title="车辆与地区信息" size="small" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={createCase}
          initialValues={{ region_code: "310000" }}
        >
          <Space wrap size={16} align="start">
            <Form.Item
              name="vehicle_model"
              label="车型"
              rules={[{ required: true, message: "请选择车型" }]}
              style={{ width: 360 }}
            >
              <Select
                showSearch
                allowClear
                optionFilterProp="label"
                placeholder="输入品牌或车系搜索，如：朗逸"
                disabled={Boolean(caseInfo)}
                options={vehicles.map((vehicle) => ({
                  value: vehicle.code,
                  label: `${vehicle.brand} ${vehicle.series}（${vehicle.year_from}-${vehicle.year_to} ${vehicle.trim}）`,
                }))}
                onChange={(code: string) => {
                  const vehicle = vehicles.find((item) => item.code === code) || null;
                  setSelectedVehicle(vehicle);
                  form.setFieldValue("vehicle_year", undefined);
                }}
              />
            </Form.Item>
            <Form.Item
              name="vehicle_year"
              label="年款"
              rules={[{ required: true, message: "请选择年款" }]}
              style={{ width: 130 }}
            >
              <Select
                placeholder="选择年款"
                disabled={!selectedVehicle || Boolean(caseInfo)}
                options={yearOptions}
              />
            </Form.Item>
            <Form.Item name="region_code" label="地区" style={{ width: 200 }}>
              <Select
                disabled={Boolean(caseInfo)}
                options={regions.map((r) => ({
                  value: r.region_code,
                  label: `${r.region_name}（${r.labor_rate} 元/工时）`,
                }))}
              />
            </Form.Item>
            <Form.Item label=" ">
              <Button type="primary" htmlType="submit" loading={creating} disabled={Boolean(caseInfo)}>
                创建案件
              </Button>
            </Form.Item>
          </Space>
          <div className="muted">
            车型与年款共同决定配件价格，请按行驶证选择具体年款。车型库由管理员维护；
            未找到对应车辆时，请联系管理员补充车型主数据。
          </div>
        </Form>
        {caseInfo && (
          <Alert
            type="success"
            showIcon
            message={`案件编号 ${caseInfo.case_no}，地区 ${caseInfo.region_name}`}
            description="车辆信息已锁定。继续上传损伤图片，上传完成后发起分析。"
          />
        )}
      </Card>

      <Card title="损伤图片" size="small" style={{ marginBottom: 16 }}>
        {!caseInfo && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="可以先选择图片：填写上方车辆信息并点击“创建案件”后，已选图片会自动上传。"
          />
        )}
        <Upload.Dragger
          multiple
          accept="image/*"
          listType="picture"
          beforeUpload={() => false}
          fileList={fileList}
          onChange={({ fileList: list }) => {
            if (list.length > remaining) {
              message.warning(`单个案件最多 ${MAX_IMAGES} 张图片，本次最多再选 ${remaining} 张`);
            }
            setFileList(list.slice(0, remaining));
          }}
          disabled={remaining === 0}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽车辆损伤照片到此处</p>
          <p className="ant-upload-hint">
            支持 jpg / png / bmp / webp，单张不超过 20 MB，单案最多 {MAX_IMAGES} 张
          </p>
        </Upload.Dragger>
        <Space style={{ marginTop: 12 }}>
          <Button
            onClick={uploadImages}
            loading={uploading}
            disabled={!fileList.length || remaining === 0}
          >
            上传图片
          </Button>
          <span className="muted">
            已上传 {images.length} 张，剩余可上传 {remaining} 张
          </span>
        </Space>
        {images.length > 0 && (
          <div className="thumb-row">
            {images.map((image) => (
              <img key={image.id} src={image.url} className="thumb" alt={image.original_name} />
            ))}
          </div>
        )}
      </Card>

      <Card size="small">
        <Space>
          <Button
            type="primary"
            onClick={analyze}
            loading={analyzing}
            disabled={!caseInfo || images.length === 0}
          >
            发起损伤分析
          </Button>
          <Button onClick={() => navigate("/")}>返回案件列表</Button>
          {images.length > 0 && (
            <Button type="link" onClick={() => navigate(`/cases/${caseInfo!.id}`)}>
              先进入工作台
            </Button>
          )}
        </Space>
      </Card>
    </div>
  );
}
