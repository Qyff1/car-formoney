#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_cardd_ema.py — 训练 YOLOv8s-seg + P2 + C2f-EMA 注意力（可选消融，第 4 阶段）

用途：
    在 P2 改进模型基础上叠加 C2f-EMA 注意力（将 backbone/neck 全部 C2f 替换为
    C2f_EMA，EMA 见 arXiv:2305.13563），回答实验问题 2：EMA 是否在 P2 基础上
    继续带来收益。固定设置与基线/P2 完全一致，保证三组指标可比。

固定设置（勿随意改动）：
    model=config/yolov8s-seg-p2-ema.yaml（scale=s，C2f_EMA 替换全部 C2f）
    预训练：yolov8s-seg.pt 按"同名且形状一致"部分迁移（EMA 分支随机初始化）
    data=config/cardd-seg.yaml  imgsz=640  epochs=200  patience=50
    batch=-1  seed=42  close_mosaic=15  cos_lr=True
    project=runs/cardd  name=yolov8s_seg_ema

注意：
    EMA 注意力增加少量参数与计算，P2 高分辨率层本身耗时较高；batch=-1 自动适配。
    --epochs 可临时调小用于短跑验证流程。

用法：
    完整训练：  python scripts/train_cardd_ema.py
    短跑验证：  python scripts/train_cardd_ema.py --epochs 3 \
                    --project runs/smoke --name smoke_ema
    断点续训：  python scripts/train_cardd_ema.py --resume
"""

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_YAML = PROJECT_ROOT / "config" / "cardd-seg.yaml"
EMA_YAML = PROJECT_ROOT / "config" / "yolov8s-seg-p2-ema.yaml"
LABELS_DIR = PROJECT_ROOT / "data" / "processed" / "cardd_yolo_seg" / "labels"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练 YOLOv8s-seg + P2 + C2f-EMA 注意力")
    p.add_argument("--epochs", type=int, default=200, help="训练轮数（短跑验证时调小）")
    p.add_argument("--patience", type=int, default=50, help="提前停止容忍轮数")
    p.add_argument("--batch", type=int, default=-1, help="batch=-1 自动显存适配")
    p.add_argument("--imgsz", type=int, default=640, help="训练输入尺寸，与基线/P2 一致以保证可比")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--project", type=str, default="runs/cardd", help="训练输出根目录")
    p.add_argument("--name", type=str, default="yolov8s_seg_ema", help="本次运行目录名")
    p.add_argument("--device", type=int, default=0, help="GPU 设备号")
    p.add_argument("--resume", action="store_true",
                   help="从 runs/cardd/<name>/weights/last.pt 断点续训；续训时其余超参忽略，"
                        "ultralytics 从 run 目录 args.yaml 恢复 epoch/optimizer/lr")
    return p.parse_args()


def dataset_hash() -> str:
    """对全部 YOLO 标签文件计算 SHA256，作为数据集版本指纹。"""
    h = hashlib.sha256()
    for lp in sorted(LABELS_DIR.rglob("*.txt")):
        h.update(lp.read_bytes())
        h.update(b"\n")
    return h.hexdigest()


def gpu_info() -> dict:
    return {
        "name": torch.cuda.get_device_name(0),
        "total_mib": round(torch.cuda.get_device_properties(0).total_memory / 1024 / 1024),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
    }


def git_state() -> dict:
    """记录 Git 提交状态（当前仓库无提交，如实记录）。"""
    try:
        head = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10)
        branch = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10)
        return {"commit": head.stdout.strip() or "无提交", "branch": branch.stdout.strip()}
    except Exception as exc:  # git 不可用时如实记录
        return {"commit": "不可用", "branch": "不可用", "error": str(exc)}


def main() -> None:
    args = parse_args()
    from ultralytics import YOLO  # 延迟导入，先打印环境信息

    snapshot = {
        "tool": "scripts/train_cardd_ema.py",
        "model_yaml": str(EMA_YAML),
        "pretrained": "yolov8s-seg.pt（部分迁移：同名且形状一致的层，EMA 分支随机初始化）",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": platform.python_version(),
        "gpu": gpu_info(),
        "git": git_state(),
        "dataset_sha256": dataset_hash(),
        "data_yaml": str(DATA_YAML),
        "train_args": vars(args),
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))

    run_dir = Path(args.project) / args.name

    if args.resume:
        last_pt = run_dir / "weights" / "last.pt"
        if not last_pt.exists():
            raise SystemExit(f"[train] 断点不存在，无法续训: {last_pt}")
        model = YOLO(str(last_pt))
        model.train(resume=True, device=args.device, exist_ok=True)
        print(f"[train] 断点续训完成，再次中断可继续 --resume 续训: {run_dir}")
        return

    model = YOLO(str(EMA_YAML))  # 按 yaml 构建 P2+EMA 模型（scale=s）
    model.load("yolov8s-seg.pt")  # 迁移预训练：共享层按名匹配，EMA 分支随机初始化
    model.train(
        data=str(DATA_YAML),
        imgsz=args.imgsz,
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        seed=args.seed,
        close_mosaic=15,
        cos_lr=True,
        project=args.project,
        name=args.name,
        device=args.device,
        workers=0,  # 本机 16GB 内存/页面文件较小，Windows 多进程 worker 加载 CUDA DLL 会触发 WinError 1455；SSD 下主进程加载数据无性能影响
        exist_ok=True,
    )

    snapshot["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    snapshot["run_dir"] = str(run_dir)
    (run_dir / "train_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"训练完成，快照已保存: {run_dir / 'train_snapshot.json'}")


if __name__ == "__main__":
    main()
