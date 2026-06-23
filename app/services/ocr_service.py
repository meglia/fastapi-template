"""PaddleOCR 文字识别服务 — 单例模式封装推理。"""

import time
import threading

import numpy as np
from paddleocr import PaddleOCR

from app.core.config import settings
from app.schemas.ocr import OCRBlock, OCRResponse


class OCRService:
    """OCR 推理单例。"""

    _instance: "OCRService | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "OCRService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._ocr: PaddleOCR | None = None
        self._initialized = True

    @property
    def ocr(self) -> PaddleOCR:
        if self._ocr is None:
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=settings.OCR_LANG,
                use_gpu=settings.OCR_USE_GPU,
                det_model_dir=settings.OCR_DET_MODEL_DIR,
                rec_model_dir=settings.OCR_REC_MODEL_DIR,
            )
        return self._ocr

    def predict(self, image: np.ndarray, filename: str = "") -> OCRResponse:
        """对单张 numpy 图片执行 OCR。"""
        t0 = time.perf_counter()
        raw = self.ocr.ocr(image, cls=True)
        elapsed = (time.perf_counter() - t0) * 1000

        blocks: list[OCRBlock] = []
        if raw and raw[0]:
            for line in raw[0]:
                box, (text, conf) = line
                blocks.append(
                    OCRBlock(
                        text=text,
                        confidence=conf,
                        box=[[int(p[0]), int(p[1])] for p in box],
                    )
                )

        return OCRResponse(
            filename=filename,
            blocks=blocks,
            inference_time_ms=elapsed,
        )


# 模块级便捷引用
ocr_service = OCRService()
