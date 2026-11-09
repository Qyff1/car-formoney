# 车辆损伤智能定损系统

基于 YOLOv8s-seg 的车辆损伤识别与规则化定损报价系统。上传事故车辆照片后，系统自动分割损伤区域、识别损伤类型，结合车型/年款配件价、标准工时与地区费率生成维修报价，并支持审核确认与定损报告导出。

## 功能概览

- **损伤识别**：6 类损伤分割（凹陷 dent、刮擦 scratch、裂纹 crack、玻璃破碎 glass shatter、车灯破损 lamp broken、轮胎损伤 tire flat），输出掩膜、置信度与损伤面积占比。
- **部件预填**：按损伤类型自动预填受损部件（系统初判，人工可改）。
- **规则定价**：`维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价`，配件价按「车型 + 年款 + 损伤严重度」取值。
- **车型库**：内置 21 条车型主数据（1 条通用兜底 + 20 款主流车）、12 类通用配件与 1392 条车型年款专属配件价。
- **模型版本管理**：基线与 P2 改进版同时入库，管理员可切换线上推理模型。
- **角色与审计**：查勘定损员 / 审核员 / 系统管理员三角色，关键操作写审计日志。
- **报告**：报价审核确认后生成定损报告（HTML）。

## 目录结构

```
car-formoney/
├─ services/
│  ├─ api/app/            # FastAPI 后端：路由、模型、权限、定价引擎、种子数据
│  └─ inference/          # YOLOv8-seg 推理封装
├─ web/                   # React 18 + TypeScript + Vite + Ant Design 前端
│  └─ src/{pages,components,api,auth}
├─ config/
│  ├─ pricing/            # 车型库、配件价、工时/材料、地区费率、定价规则
│  ├─ cardd-seg.yaml      # CarDD 数据集配置
│  └─ yolov8s-seg-p2*.yaml# P2 改进模型配置
├─ scripts/               # 数据准备、训练、固定集评测脚本
├─ tests/                 # pytest 用例
├─ data/
│  ├─ test_images/        # 12 张演示用损伤样例图（每类 2 张）
│  └─ processed/          # 训练数据派生目录（不提交）
├─ runs/cardd/
│  ├─ yolov8s_seg_baseline/weights/best.pt    # 基线权重（随仓库提供）
│  └─ yolov8s_seg_p2_mask320/weights/best.pt # P2 权重（随仓库提供）
├─ setup.ps1              # Windows 一键安装依赖
├─ 车辆定损系统.bat        # Windows 一键启动
└─ requirements.txt
```

## 技术栈

| 层 | 选型 |
| --- | --- |
| 模型 | YOLOv8s-seg（ultralytics 8.3.x），输入 640，mask 160 |
| 推理 | PyTorch 2.x + CUDA 12.8 |
| 后端 | FastAPI、SQLAlchemy 2、SQLite、PyJWT |
| 前端 | React 18、TypeScript、Vite 5、Ant Design 5 |
| 数据 | CarDD（COCO 格式，训练 2816 / 验证 810 / 测试 374） |

## 环境要求

- Windows 10/11（启动脚本为 PowerShell / bat），Python 3.10–3.12（推荐 3.12）
- Node.js 18+
- NVIDIA 显卡 + 驱动（训练与 GPU 推理）；无 GPU 时可用 CPU 推理，但速度较慢

---

# 一、给 AI 的快速开始

> 本节面向自动化编码助手。执行前请确认工作目录为仓库根目录 `d:\car-formoney`（或你的克隆路径）。

## 1. 一次性环境准备

```powershell
# 1) 创建虚拟环境
python -m venv .venv

# 2) 先装 GPU 版 PyTorch（CUDA 12.8），不要装 CPU 版
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 3) 再装其余依赖
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4) 前端依赖
cd web; npm install; cd ..
```

缓存目录统一放 D 盘，避免占用系统盘（可选）：

```powershell
$env:PIP_CACHE_DIR = "D:\car-formoney\.cache\pip"
$env:TORCH_HOME    = "D:\car-formoney\.cache\torch"
$env:YOLO_CONFIG_DIR = "D:\car-formoney\.cache\ultralytics"
```

等价的一键脚本：`powershell -ExecutionPolicy Bypass -File .\setup.ps1`。

## 2. 启动与自检

```powershell
# 后端（8000）
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000

# 前端（5173，另开终端）
cd web; npm run dev -- --host 127.0.0.1 --port 5173

# 健康检查
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

- API 文档：<http://127.0.0.1:8000/docs>
- 前端界面：<http://127.0.0.1:5173>
- 默认账号：`周显鑫0`（查勘定损员）、`周显鑫1`（审核员）、`周显鑫2`（系统管理员），密码统一 `Cardd@2026`

## 3. AI 必须遵守的约束

1. 依赖必须使用 GPU 版 PyTorch（cu128），禁止安装 CPU 版；安装顺序为先 torch/torchvision、再 requirements。
2. 运行 Python 一律使用 `.\.venv\Scripts\python.exe`，不要用全局 Python。
3. 不要提交 `data/raw/`、`data/uploads/`、`data/app.db`、`runs/`（两个 best.pt 除外）、`docs/`、日志与缓存。
4. 不要把 CarDD 图片与"真实维修结算价"直接用于费用回归训练；报价必须走规则引擎。
5. 测试集不参与调参；对比实验统一使用 imgsz=640 与同一评测脚本。
6. 改前端后执行 `npx tsc -b`；改后端后执行 `pytest tests -q`，并重启后端验证接口。
7. 端口 8000/5173 已被占用时不要重复启动；先确认是否已有实例。

## 4. 常用校验命令

```powershell
# 后端测试
.\.venv\Scripts\python.exe -m pytest tests -q

# 前端类型检查与构建
cd web; npx tsc -b; npm run build; cd ..

# 数据库重置（会清空案件与账号，重新初始化演示数据）
Remove-Item data\app.db
```

---

# 二、依赖安装（人工）

1. 安装 Python 3.12 与 Node.js 18+，确保 `python`、`node`、`npm` 在 PATH 中。
2. 在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

脚本会创建 `.venv`、安装 cu128 版 PyTorch 与 `requirements.txt` 全部依赖，并打印 GPU / ultralytics 版本。可重复执行，已完成的步骤自动跳过。

3. 安装前端依赖：`cd web; npm install`。

---

# 三、给人看的操作指南

## 1. 启动

双击根目录的 `车辆定损系统.bat`。脚本会检查环境、分别在两个窗口启动前后端，等两个服务就绪后自动打开浏览器（最多 90 秒）。使用完毕关闭这两个命令行窗口即可停止服务。

## 2. 业务操作流程

| 步骤 | 操作 | 角色 |
| --- | --- | --- |
| 1 | 登录系统 | 全部 |
| 2 | 新建案件：从车型库搜索选择车辆，再选择年款（年款决定配件价） | 查勘定损员 |
| 3 | 上传损伤照片（可先选图，创建案件后自动上传；单案最多 10 张、单张 20MB） | 查勘定损员 |
| 4 | 点击"开始分析"，查看损伤掩膜、类型、置信度与面积占比 | 查勘定损员 |
| 5 | 在工作台逐条确认损伤：部件（系统已预填）、严重度、维修动作，保存并确认 | 查勘定损员 |
| 6 | 进入报价页试算，生成报价单 | 查勘定损员 |
| 7 | 审核报价并确认 | 审核员 |
| 8 | 生成并下载定损报告（需报价已确认） | 查勘定损员 / 管理员 |

## 3. 角色权限

| 角色 | 账号 | 权限 |
| --- | --- | --- |
| 查勘定损员 | 周显鑫0 | 建案、上传、分析、确认损伤、报价、生成报告 |
| 审核员 | 周显鑫1 | 查看案件、复核并确认报价，不能建案/上传/分析/改损伤 |
| 系统管理员 | 周显鑫2 | 主数据维护、模型版本切换、审计日志 |

## 4. 模型版本管理

「模型版本管理」页列出两个交付模型，管理员可"设为线上"：

| 模型 | Mask mAP50-95 | Box mAP50-95 | 参数量 | P50 时延 |
| --- | --- | --- | --- | --- |
| yolov8s-seg-baseline（默认） | 0.5612 | 0.5943 | 11.79 M | 21.3 ms |
| yolov8s-seg-p2-mask320 | 0.5536 | 0.5836 | 11.25 M | 27.4 ms |

指标为 CarDD 测试集 374 张、imgsz=640 的统一口径评测结果。P2 版本未达改进目标，保留作为对照。

切换模型只影响之后发起的分析，已生成的损伤结果不变。

## 5. 定价规则

```
维修费用 = 配件费 + 材料费 + 标准工时 × 地区工时单价
```

- **配件费**：按「车型 + 年款 + 配件 + 严重度」取值。更换类动作按严重度取低/中/高位价；同车型不同年款价格不同（以区间最新年为基准，每增加一年乘 0.96，最低 65%）。
- **材料费**：按动作与严重度档取配置值。
- **工时费**：标准工时 × 所选地区工时单价。
- 车型未命中时回退通用配件价；配件目录缺失该部件时报价会明确报错，不会静默给 0。

> 价格来自公开资料测算（中保研零整比均值 × 指导价中值等），仅用于系统演示，不代表厂商报价或保险结算价。

## 6. 演示数据

`data/test_images/` 提供 12 张 CarDD 测试集样例图（每类 2 张），可直接用于上传演示。图片来源于 CarDD 公开数据集，仅作功能演示。

---

# 四、配置项

通过环境变量覆盖（也可写入根目录 `.env`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_DB_PATH` | `data/app.db` | SQLite 数据库路径 |
| `APP_JWT_SECRET` | 内置开发密钥 | 生产环境务必修改 |
| `APP_JWT_EXPIRE_MINUTES` | `480` | 令牌有效期 |
| `APP_MODEL_VERSION` | `yolov8s-seg-baseline` | 首次初始化时启用的模型名 |
| `APP_INFER_DEVICE` | `0` | 推理设备，无 GPU 用 `cpu` |
| `APP_INFER_IMGSZ` | `640` | 推理输入尺寸 |
| `APP_INFER_CONF` | `0.25` | 置信度阈值 |
| `APP_INFER_IOU` | `0.7` | NMS IoU 阈值 |
| `APP_REVIEW_CONFIDENCE` | `0.5` | 低于该置信度标记需复核 |
| `APP_MAX_UPLOAD_MB` | `20` | 单图大小上限 |
| `APP_MAX_IMAGES_PER_CASE` | `10` | 单案图片数上限 |

首次启动会自动建库并初始化：账号、车型库、配件价、工时/材料、地区费率、定价规则与两个模型版本。

# 五、常见问题

- **启动报"未找到 .venv / node_modules"**：先执行 `setup.ps1` 与 `cd web; npm install`。
- **报价预览为 0**：损伤尚未确认。在工作台确认损伤后再试算。
- **模型加载失败 / 推理报 CUDA 错误**：确认安装的是 cu128 版 PyTorch；无 GPU 时设置 `APP_INFER_DEVICE=cpu`。
- **车型下拉里找不到车辆**：车型库由管理员维护，可补充 `config/pricing/vehicle_models.json` 后重建数据库，或在「价格规则」页维护主数据。
- **端口被占用**：8000（后端）或 5173（前端）已有实例，关闭旧窗口或改端口启动。

# 六、数据与致谢

- 损伤数据：[CarDD](https://cardd-ustc.github.io/) 车辆损伤数据集（COCO 格式）。
- 车辆与配件价格：公开资料整理与测算，仅用于演示。
