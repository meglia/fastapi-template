"""YOLO 目标检测服务 — 单例模式封装 ultralytics 推理。"""

import time
import threading
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from app.core.config import settings
from app.schemas.yolo import DetectionBox, YoloResponse


class YoloService:
    """YOLO 推理单例。"""

    _instance: "YoloService | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "YoloService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._model: YOLO | None = None
        self._initialized = True

    @property
    def model(self) -> YOLO:
        if self._model is None:
            self._model = YOLO(settings.YOLO_MODEL_PATH)
        return self._model

    def predict(self, image: np.ndarray, filename: str = "") -> YoloResponse:
        """对单张 numpy 图片执行检测。"""
        t0 = time.perf_counter()
        results = self.model(
            image,
            conf=settings.YOLO_CONF_THRESHOLD,
            iou=settings.YOLO_IOU_THRESHOLD,
            verbose=False,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        detections: list[DetectionBox] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    DetectionBox(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=float(box.conf[0]),
                        class_id=int(box.cls[0]),
                        class_name=self.model.names.get(int(box.cls[0]), "unknown"),
                    )
                )

        return YoloResponse(
            filename=filename,
            detections=detections,
            inference_time_ms=elapsed,
        )


# 模块级便捷引用
yolo_service = YoloService()
