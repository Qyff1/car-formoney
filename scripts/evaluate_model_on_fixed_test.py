#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_model_on_fixed_test.py — 在固定测试图集上评测模型并保存核对产物

用途：
    对任意已训练权重（基线 / P2 / P2+C2f-EMA）在**同一批固定 50 张测试图**
    上评测，输出可并排核对的产物：
      - 50 张掩膜叠加预测图（runs/cardd/<模型>/verify/images/overlays/）
      - results.json：整体 Mask mAP50-95/mAP50、每类 Mask AP50-95、
        参数量、单图推理时延 P50/P95、固定测试图清单
    三版模型共用本脚本与同一固定图集，保证版本间结果可比。

全量测试集指标（374 张）与固定 50 张可视化分开：前者是权威精度，
后者用于版本间图像级核对。

用法：
    python scripts/evaluate_model_on_fixed_test.py \
        --weights runs/cardd/yolov8s_seg_baseline/weights/best.pt \
        --out runs/cardd/yolov8s_seg_baseline/verify
"""

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_YAML = PROJECT_ROOT / "config" / "cardd-seg.yaml"
TEST_IMG_DIR = PROJECT_ROOT / "data" / "processed" / "cardd_yolo_seg" / "images" / "test"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="固定测试图集评测")
    p.add_argument("--weights", required=True, help="模型权重路径")
    p.add_argument("--out", required=True, help="输出目录（如 runs/cardd/<模型>/verify）")
    p.add_argument("--num-images", type=int, default=50, help="固定核验图数量")
    p.add_argument("--seed", type=int, default=42, help="固定抽样种子")
    p.add_argument("--device", type=int, default=0, help="GPU 设备号")
    p.add_argument("--imgsz", type=int, default=640, help="推理输入尺寸，与训练一致（三组模型统一 640）")
    return p.parse_args()


def pick_fixed_images(num: int, seed: int) -> list:
    """按固定种子从测试集抽取核验图，保证各模型版本看到同一批图。"""
    imgs = sorted(TEST_IMG_DIR.glob("*.jpg"))
    rng = random.Random(seed)
    return [str(p) for p in rng.sample(imgs, min(num, len(imgs)))]


def main() -> None:
    args = parse_args()
    from ultralytics import YOLO

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    nc = len(model.names)
    params = sum(p.numel() for p in model.model.parameters())

    # 真值掩膜下采样比须与模型原型的掩膜分辨率一致（P2 模型为 2，标准模型为 4），
    # 否则评测时预测掩膜会被降采样，抹掉高分辨率带来的精度收益
    mask_ratio = max(int(model.model.stride[0]) // 2, 1)

    # 1) 全量测试集权威指标（374 张）
    val = model.val(data=str(DATA_YAML), split="test", imgsz=args.imgsz,
                    device=args.device, batch=1, verbose=False,
                    mask_ratio=mask_ratio,
                    workers=0, exist_ok=True)  # workers=0：避免本机 Windows 多进程加载 CUDA DLL 触发 WinError 1455
    rdict = val.results_dict
    per_class_ap = {}
    maps = val.seg.maps if hasattr(val, "seg") else val.maps
    ap_idx = val.seg.ap_class_index if hasattr(val, "seg") else val.ap_class_index
    for i, idx in enumerate(ap_idx):
        per_class_ap[model.names[int(idx)]] = float(maps[i]) if maps[i] >= 0 else None

    # 2) 固定 50 张核验图推理时延与叠加图
    fixed_imgs = pick_fixed_images(args.num_images, args.seed)
    latencies_ms = []
    for img in fixed_imgs:
        t0 = time.perf_counter()
        model.predict(img, imgsz=args.imgsz, device=args.device,
                      verbose=False, conf=0.25, iou=0.7)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
    lat_ms = np.array(latencies_ms)

    model.predict(fixed_imgs, imgsz=args.imgsz, device=args.device,
                  conf=0.25, iou=0.7, save=True, verbose=False,
                  project=str(out_dir / "images"), name="overlays")

    results = {
        "tool": "scripts/evaluate_model_on_fixed_test.py",
        "weights": args.weights,
        "fixed_test_images": [Path(p).name for p in fixed_imgs],
        "fixed_image_count": len(fixed_imgs),
        "seed": args.seed,
        "imgsz": args.imgsz,
        "mask_ratio": mask_ratio,
        "parameters": params,
        "overall_mask_map50_95": rdict.get("metrics/mAP50-95(M)"),
        "overall_mask_map50": rdict.get("metrics/mAP50(M)"),
        "overall_box_map50_95": rdict.get("metrics/mAP50-95(B)"),
        "per_class_mask_ap50_95": per_class_ap,
        "latency_ms": {
            "p50": round(float(np.percentile(lat_ms, 50)), 1),
            "p95": round(float(np.percentile(lat_ms, 95)), 1),
            "mean": round(float(lat_ms.mean()), 1),
            "n": len(lat_ms),
        },
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"核对产物已保存: {out_dir}")


if __name__ == "__main__":
    main()
