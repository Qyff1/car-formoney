# ============================================================
# 保险理赔图像智能定损系统 — 一键环境安装脚本（Windows / PowerShell）
#
# 用法（二选一）：
#   1) .\setup.ps1
#   2) powershell -ExecutionPolicy Bypass -File setup.ps1
#
# 作用：创建 .venv 虚拟环境 -> 安装 GPU 版 PyTorch（CUDA 12.8 / cu128）
#       -> 安装 requirements.txt 全部依赖 -> 验证 GPU 与 ultralytics。
# 可重复执行：已安装的步骤自动跳过。
# 前置要求：Python 3.10+（推荐 3.12）已安装并加入 PATH，NVIDIA 显卡 + 驱动。
# ============================================================

$ErrorActionPreference = 'Stop'
$Root   = $PSScriptRoot
$Venv   = Join-Path $Root '.venv'
$PipCache = Join-Path $Root '.cache\pip'

# ---------- 1. 检查 Python ----------
$Py = Get-Command python -ErrorAction SilentlyContinue
if (-not $Py) {
    Write-Host '[失败] 未找到 python，请先安装 Python 3.10+ 并勾选 "Add to PATH"' -ForegroundColor Red
    exit 1
}

# ---------- 2. 创建虚拟环境（幂等） ----------
$VenvPy = Join-Path $Venv 'Scripts\python.exe'
if (Test-Path $VenvPy) {
    Write-Host '[1/4] 虚拟环境 .venv 已存在，跳过创建' -ForegroundColor Yellow
} else {
    Write-Host '[1/4] 创建虚拟环境 .venv ...' -ForegroundColor Cyan
    python -m venv $Venv
}
$env:PIP_CACHE_DIR = $PipCache   # 缓存放 D 盘同仓库目录，避免占用系统盘

# ---------- 3. 安装 GPU 版 PyTorch（cu128，官方源） ----------
Write-Host '[2/4] 安装 GPU 版 PyTorch（CUDA 12.8 / cu128，约 2.5GB）...' -ForegroundColor Cyan
& $VenvPy -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { Write-Host '[失败] PyTorch 安装失败，请检查网络' -ForegroundColor Red; exit 1 }

# ---------- 4. 安装项目依赖（官方 PyPI，避免镜像源构建依赖解析失败） ----------
Write-Host '[3/4] 安装项目依赖 requirements.txt ...' -ForegroundColor Cyan
& $VenvPy -m pip install -r (Join-Path $Root 'requirements.txt') --index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { Write-Host '[失败] requirements 安装失败' -ForegroundColor Red; exit 1 }

# ---------- 5. 验证环境 ----------
Write-Host '[4/4] 验证环境 ...' -ForegroundColor Cyan
& $VenvPy -c @"
import torch, sys, ultralytics
print('python      :', sys.version.split()[0])
print('torch       :', torch.__version__)
print('cuda_avail  :', torch.cuda.is_available())
print('ultralytics :', ultralytics.__version__)
if torch.cuda.is_available():
    print('gpu         :', torch.cuda.get_device_name(0), '| cuda', torch.version.cuda)
else:
    print('[警告] 未检测到可用 GPU：请确认已安装 NVIDIA 显卡驱动。模型训练需要 GPU。')
"@

if ($LASTEXITCODE -ne 0) { Write-Host '[失败] 环境验证未通过' -ForegroundColor Red; exit 1 }

Write-Host ''
Write-Host '==============================================' -ForegroundColor Green
Write-Host ' 环境安装完成。后续使用本环境：'              -ForegroundColor Green
Write-Host '   .\.venv\Scripts\activate'                 -ForegroundColor Green
Write-Host '   python scripts\\<脚本名>.py'               -ForegroundColor Green
Write-Host '==============================================' -ForegroundColor Green
