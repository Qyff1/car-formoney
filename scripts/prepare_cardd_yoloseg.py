#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_cardd_yoloseg.py — 第 1 阶段数据准备：CarDD COCO → YOLO Seg 训练格式

用途：
    1. 解析 CarDD_COCO 官方的 instances_{train,val,test}2017.json；
    2. 将多边形分割标注转换为 YOLO Seg 的归一化多边形标签（txt）；
    3. 将原图复制到 data/processed/cardd_yolo_seg/images/<split>；
    4. 生成类别频次、掩膜面积、每图实例数等质量统计；
    5. 输出 samples_review.csv（每类随机抽样 >= 50 个实例，供人工核对）；
    6. 记录空标注图、损坏文件、异常标注等不可用样本清单；
    7. 生成 config/cardd-seg.yaml 数据配置；
    8. 生成每类 1 张掩膜叠加预览图，供直观核对转换质量。

原则：
    - 原始 data/raw/CarDD_COCO 只读，不覆盖、不修改；
    - 转换产物全部写入 data/processed/cardd_yolo_seg；
    - train/val/test 严格使用 CarDD 官方划分，图像不跨集合移动。
"""

import argparse
import csv
import json
import random
import shutil
import statistics
from pathlib import Path

from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 常量配置

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "CarDD_COCO"
ANN_DIR = RAW_DIR / "annotations"
IMG_DIR = RAW_DIR / "images"

OUT_DIR = PROJECT_ROOT / "data" / "processed" / "cardd_yolo_seg"
STATS_DIR = OUT_DIR / "stats"
PREVIEW_DIR = STATS_DIR / "previews"

DATA_YAML = PROJECT_ROOT / "config" / "cardd-seg.yaml"

# CarDD 官方 category_id → YOLO 类别索引（按官方顺序固定，勿改动）
CATEGORY_ID2IDX = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
CLASS_NAMES = ["dent", "scratch", "crack", "glass shatter", "lamp broken", "tire flat"]

SPLITS = ["train", "val", "test"]

SAMPLE_PER_CLASS = 50  # 每类随机抽样实例数下限（用于人工核对）
PREVIEW_PER_CLASS = 1  # 每类可视化预览图张数
RNG_SEED = 42


# ---------------------------------------------------------------- 工具函数

def log(msg: str) -> None:
    print(f"[prepare_cardd_yoloseg] {msg}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CarDD COCO -> YOLO Seg 转换")
    p.add_argument("--splits", nargs="+", default=SPLITS, choices=SPLITS,
                   help="要转换的数据集划分（默认全部）")
    p.add_argument("--sample-per-class", type=int, default=SAMPLE_PER_CLASS,
                   help="每类抽样人工核对实例数下限")
    p.add_argument("--seed", type=int, default=RNG_SEED, help="随机种子")
    return p.parse_args()


def load_coco(json_path: Path) -> dict:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def polygon_points_to_flat(segmentation) -> list:
    """将 COCO 分割标注转为平面坐标点列表 [x0, y0, x1, y1, ...]。"""
    pts = []
    if segmentation and isinstance(segmentation, list):
        for poly in segmentation:
            pts.extend(float(v) for v in poly)
    return pts


def normalize_and_validate(flat_pts: list, width: int, height: int):
    """
    归一化并校验多边形点。
    返回 (class_idx, 归一化后的 [x0,y0,...] 列表, 是否有效, 不可用原因)。
    """
    if len(flat_pts) < 6:  # 少于 3 个点
        return None, None, False, "多边形点数 < 3"
    if any(v < 0 for v in flat_pts):
        return None, None, False, "存在负坐标"
    n = len(flat_pts) // 2
    norm = []
    for i in range(n):
        x = flat_pts[2 * i] / width
        y = flat_pts[2 * i + 1] / height
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return None, None, False, "坐标超出图像范围"
        norm.append(round(x, 6))
        norm.append(round(y, 6))
    return norm, True, None


# ---------------------------------------------------------------- 主流程

def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    # 清理并重建输出目录（仅清理 cardd_yolo_seg 内部，不触碰原始数据）
    if OUT_DIR.exists():
        for child in OUT_DIR.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    for split in args.splits:
        (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "input_anns": {},
        "images_total": 0,
        "images_with_labels": 0,
        "images_empty": 0,
        "images_missing_file": 0,
        "instances_total": 0,
        "instances_converted": 0,
        "instances_unusable": 0,
        "unusable_reasons": {},
        "class_counts": {name: {s: 0 for s in args.splits} for name in CLASS_NAMES},
        "instances_per_image": [],
        "area_per_class": {name: [] for name in CLASS_NAMES},
    }

    # 抽样核对与预览用样本
    review_rows = []          # samples_review.csv 行
    preview_selected = {}     # class_idx -> 一条标注信息
    class_seen = {i: 0 for i in range(6)}

    # 逐划分转换
    for split in args.splits:
        log(f"--- 转换 {split} ---")
        coco = load_coco(ANN_DIR / f"instances_{split}2017.json")
        summary["input_anns"][split] = len(coco["images"])
        img_id2info = {im["id"]: im for im in coco["images"]}

        # 标注按图像聚合
        ann_by_img = {}
        for ann in coco["annotations"]:
            ann_by_img.setdefault(ann["image_id"], []).append(ann)

        for img_id, im in img_id2info.items():
            summary["images_total"] += 1
            fname = im["file_name"]
            src_img = IMG_DIR / split / fname
            if not src_img.exists():
                summary["images_missing_file"] += 1
                _append_review_row(review_rows, split, fname, reason="原图缺失")
                continue
            shutil.copy2(src_img, OUT_DIR / "images" / split / fname)

            label_lines = []
            img_area_total = 0.0
            for ann in ann_by_img.get(img_id, []):
                summary["instances_total"] += 1
                cat_idx = CATEGORY_ID2IDX.get(ann["category_id"])
                if cat_idx is None:
                    summary["instances_unusable"] += 1
                    _count_reason(summary, f"未知类别 {ann['category_id']}")
                    continue
                if ann.get("iscrowd"):
                    summary["instances_unusable"] += 1
                    _count_reason(summary, "iscrowd=1")
                    continue
                if not isinstance(ann["segmentation"], list):
                    summary["instances_unusable"] += 1
                    _count_reason(summary, "RLE/非多边形分割")
                    continue

                flat = polygon_points_to_flat(ann["segmentation"])
                norm, ok, reason = normalize_and_validate(flat, im["width"], im["height"])
                if not ok:
                    summary["instances_unusable"] += 1
                    _count_reason(summary, reason)
                    continue

                cls_name = CLASS_NAMES[cat_idx]
                line = " ".join([str(cat_idx)] + [str(v) for v in norm])
                label_lines.append(line)
                summary["instances_converted"] += 1
                summary["class_counts"][cls_name][split] += 1
                summary["area_per_class"][cls_name].append(ann["area"])
                img_area_total += ann["area"]

                # 抽样核对：每类达到下限前收集
                if class_seen[cat_idx] < args.sample_per_class:
                    review_rows.append({
                        "split": split,
                        "image_id": img_id,
                        "image_file": fname,
                        "class_id": cat_idx,
                        "class_name": cls_name,
                        "bbox": f"[{ann['bbox'][0]:.1f}, {ann['bbox'][1]:.1f}, "
                                f"{ann['bbox'][2]:.1f}, {ann['bbox'][3]:.1f}]",
                        "area": round(ann["area"], 1),
                        "poly_points": len(flat) // 2,
                    })
                    class_seen[cat_idx] += 1

                # 预览：每类 1 张（取 train 划分首条）
                if split == "train" and cat_idx not in preview_selected:
                    preview_selected[cat_idx] = {
                        "image_path": src_img,
                        "fname": fname,
                        "cls_name": cls_name,
                        "seg": flat,
                        "width": im["width"],
                        "height": im["height"],
                        "bbox": ann["bbox"],
                    }

            if label_lines:
                summary["images_with_labels"] += 1
                stem = Path(fname).stem
                (OUT_DIR / "labels" / split / f"{stem}.txt").write_text(
                    "\n".join(label_lines) + "\n", encoding="utf-8")
            else:
                summary["images_empty"] += 1
                _append_review_row(review_rows, split, fname, reason="无有效标注")

            summary["instances_per_image"].append(
                f"{fname},{len(label_lines)}")

    # 写出统计文件
    _write_stats(summary, review_rows)

    # 生成数据配置
    _write_data_yaml(DATA_YAML)

    # 生成可视化预览
    for cat_idx, info in preview_selected.items():
        _make_preview(info, PREVIEW_DIR)

    # 汇总报告
    report = _build_report(summary, review_rows, args)
    (STATS_DIR / "conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    log("完成。结果见 data/processed/cardd_yolo_seg/stats/")
    log(json.dumps({k: v for k, v in report.items()
                    if not isinstance(v, dict) or k == "class_counts"},
                   ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 辅助

def _count_reason(summary: dict, reason: str) -> None:
    summary["unusable_reasons"][reason] = summary["unusable_reasons"].get(reason, 0) + 1


def _append_review_row(rows: list, split: str, fname: str, reason: str) -> None:
    rows.append({"split": split, "image_file": fname, "reason": reason,
                 "class_name": "", "bbox": "", "area": "", "poly_points": ""})


def _write_stats(summary: dict, review_rows: list) -> None:
    # 类别频次
    with open(STATS_DIR / "class_counts.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["class_name"] + SPLITS + ["total"])
        for name in CLASS_NAMES:
            row = [summary["class_counts"][name][s] for s in SPLITS]
            w.writerow([name] + row + [sum(row)])

    # 掩膜面积统计
    with open(STATS_DIR / "mask_area_stats.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["class_name", "count", "mean_px", "median_px", "min_px",
                    "max_px", "p25_px", "p75_px"])
        for name in CLASS_NAMES:
            vals = summary["area_per_class"][name]
            if not vals:
                w.writerow([name, 0, "", "", "", "", "", ""])
                continue
            vals_sorted = sorted(vals)
            n = len(vals)
            q = lambda p: vals_sorted[min(n - 1, int(n * p))]
            w.writerow([name, n, round(statistics.mean(vals), 1),
                        round(statistics.median(vals), 1), round(min(vals), 1),
                        round(max(vals), 1), round(q(0.25), 1), round(q(0.75), 1)])

    # 每图实例数
    (STATS_DIR / "instances_per_image.csv").write_text(
        "image_file,instance_count\n" + "\n".join(summary["instances_per_image"]) + "\n",
        encoding="utf-8-sig")

    # 抽样核对表
    with open(STATS_DIR / "samples_review.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["split", "image_id", "image_file",
                                          "class_id", "class_name", "bbox",
                                          "area", "poly_points", "reason"])
        w.writeheader()
        w.writerows(review_rows)

    # 不可用样本清单
    unusable = [r for r in review_rows if r.get("reason")]
    with open(STATS_DIR / "unusable_samples.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["split", "image_file", "reason"])
        w.writeheader()
        w.writerows({"split": r["split"], "image_file": r["image_file"],
                     "reason": r["reason"]} for r in unusable)


def _write_data_yaml(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names_block = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES))
    # path 写绝对路径：ultralytics 对相对 path 按 DATASETS_DIR 解析，不按 yaml 所在目录解析
    abs_out = OUT_DIR.resolve().as_posix()
    content = (
        "# CarDD 官方划分的 YOLO Seg 数据配置（由 prepare_cardd_yoloseg.py 生成）\n"
        f"path: {abs_out}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"names:\n{names_block}\n"
    )
    path.write_text(content, encoding="utf-8")
    log(f"已生成数据配置: {path}")


def _build_report(summary: dict, review_rows: list, args: argparse.Namespace) -> dict:
    area_summary = {}
    for name in CLASS_NAMES:
        vals = summary["area_per_class"][name]
        area_summary[name] = {
            "count": len(vals),
            "mean_px": round(statistics.mean(vals), 1) if vals else None,
            "median_px": round(statistics.median(vals), 1) if vals else None,
        }
    review_counts = {}
    for r in review_rows:
        if r.get("class_name"):
            review_counts[r["class_name"]] = review_counts.get(r["class_name"], 0) + 1
    return {
        "tool": "scripts/prepare_cardd_yoloseg.py",
        "seed": args.seed,
        "input": str(RAW_DIR),
        "output": str(OUT_DIR),
        "splits": args.splits,
        "images_total": summary["images_total"],
        "images_with_labels": summary["images_with_labels"],
        "images_empty": summary["images_empty"],
        "images_missing_file": summary["images_missing_file"],
        "instances_total": summary["instances_total"],
        "instances_converted": summary["instances_converted"],
        "instances_unusable": summary["instances_unusable"],
        "unusable_reasons": summary["unusable_reasons"],
        "class_counts": summary["class_counts"],
        "mask_area": area_summary,
        "review_samples_per_class": review_counts,
        "preview_files": sorted(p.name for p in PREVIEW_DIR.glob("*.png")),
        "data_yaml": str(DATA_YAML),
    }


def _make_preview(info: dict, out_dir: Path) -> None:
    """在原图上叠加类别掩膜与边框，输出预览图。"""
    img = Image.open(info["image_path"]).convert("RGB")
    draw = ImageDraw.Draw(img)
    flat = info["seg"]
    pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
    if len(pts) >= 3:
        draw.polygon(pts, outline=(255, 0, 0), width=3)
    bx, by, bw, bh = [float(v) for v in info["bbox"]]
    draw.rectangle([bx, by, bx + bw, by + bh], outline=(0, 0, 255), width=3)
    draw.text((bx, max(by - 18, 4)), info["cls_name"], fill=(255, 0, 0))
    out_path = out_dir / f"preview_{info['cls_name']}_{Path(info['fname']).stem}.png"
    img.save(out_path)
    log(f"已生成预览图: {out_path.name}")


if __name__ == "__main__":
    main()
