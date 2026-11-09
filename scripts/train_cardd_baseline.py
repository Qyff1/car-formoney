#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_cardd_baseline.py — 训练 YOLOv8s-seg 基线（第 2 阶段）

用途：
    按技术方案 5.2 的固定设置训练基线，并在训练前记录环境与数据快照
    （数据集哈希、GPU/显存、PyTorch/ultralytics 版本、训练配置、Git 状态），
    供后续 P2/消融实验对齐环境与复现核对。

固定设置（与方案一致，勿随意改动）：
    model=yolov8s-seg.pt  data=config/cardd-seg.yaml  imgsz=640
    epochs=200  patience=50  batch=-1  seed=42  close_mosaic=15  cos_lr=True
    project=runs/cardd  name=yolov8s_seg_baseline

注意：
    显存较小（RTX 4050 6GB）时 batch=-1 自动适配，训练耗时可能较长，
    靠 patience=50 提前停止。--epochs 可临时调小用于短跑验证流程。

用法：
    完整训练：  python scripts/train_cardd_baseline.py
    短跑验证：  python scripts/train_cardd_baseline.py --epochs 5 \
                    --project runs/smoke --name smoke_test
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
LABELS_DIR = PROJECT_ROOT / "data" / "processed" / "cardd_yolo_seg" / "labels"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练 YOLOv8s-seg 基线")
    p.add_argument("--epochs", type=int, default=200, help="训练轮数（短跑验证时调小）")
    p.add_argument("--patience", type=int, default=50, help="提前停止容忍轮数")
    p.add_argument("--batch", type=int, default=-1, help="batch=-1 自动显存适配")
    p.add_argument("--imgsz", type=int, default=640, help="训练输入尺寸（6GB 显存下 640 可显著提速，三组模型统一以保证可比性）")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--project", type=str, default="runs/cardd", help="训练输出根目录")
    p.add_argument("--name", type=str, default="yolov8s_seg_baseline", help="本次运行目录名")
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
        "tool": "scripts/train_cardd_baseline.py",
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

    model = YOLO("yolov8s-seg.pt")  # 预训练权重，缺失时按缓存规则下载到 D 盘
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
