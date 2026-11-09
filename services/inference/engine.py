# -*- coding: utf-8 -*-
"""YOLOv8-seg 推理封装：返回损伤实例与叠加可视化。"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

_ENGINES: dict[tuple, "DamageSegmenter"] = {}
_LOCK = threading.Lock()


class DamageSegmenter:
    def __init__(self, weights: str, imgsz: int = 640, conf: float = 0.25,
                 iou: float = 0.7, device: str = "0"):
        self.weights = str(weights)
        self.imgsz = imgsz
        self.conf = conf
        self.iou = iou
        self.device = device
        self._model = None
        self._infer_lock = threading.Lock()

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO

            if not Path(self.weights).exists():
                raise FileNotFoundError(f"模型权重不存在：{self.weights}")
            self._model = YOLO(self.weights)
        return self._model

    def predict(self, image_path: str, overlay_path: str) -> list[dict]:
        import cv2

        model = self._load()
        with self._infer_lock:
            results = model.predict(
                source=image_path,
                imgsz=self.imgsz,
                conf=self.conf,
                iou=self.iou,
                device=self.device,
                verbose=False,
            )
        result = results[0]
        height, width = result.orig_shape
        names = result.names

        instances: list[dict] = []
        if result.masks is not None and result.boxes is not None:
            for index, polygon in enumerate(result.masks.xy):
                points = np.asarray(polygon, dtype=np.float64)
                if points.ndim != 2 or points.shape[0] < 3:
                    continue
                x = points[:, 0]
                y = points[:, 1]
                area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
                class_id = int(result.boxes.cls[index].item())
                instances.append(
                    {
                        "class_id": class_id,
                        "class_name": names.get(class_id, str(class_id)),
                        "confidence": float(result.boxes.conf[index].item()),
                        "bbox": [round(float(v), 2) for v in result.boxes.xyxy[index].tolist()],
                        "polygons": [[[round(float(px), 2), round(float(py), 2)] for px, py in points]],
                        "mask_area_ratio": float(area / (width * height)) if width and height else 0.0,
                    }
                )

        plotted = result.plot()
        Path(overlay_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(overlay_path), plotted)
        return instances


def get_segmenter(weights: str, imgsz: int, conf: float, iou: float, device: str) -> DamageSegmenter:
    key = (str(weights), imgsz, conf, iou, str(device))
    with _LOCK:
        engine = _ENGINES.get(key)
        if engine is None:
            engine = DamageSegmenter(weights, imgsz, conf, iou, device)
            _ENGINES[key] = engine
    return engine
