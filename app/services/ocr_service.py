"""OCR 服务 — RapidOCR 单例封装，提供文字检测与识别能力。"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
from rapidocr import RapidOCR

logger = logging.getLogger(__name__)


class OcrService:
    """OCR 识别服务（单例，惰性初始化）。

    封装 RapidOCR 引擎，支持：
    - 传入图片路径 / URL / numpy 数组
    - 文字检测（detection）
    - 文字识别（recognition）
    - 方向分类（classification）
    """

    def __init__(self) -> None:
        self._engine: RapidOCR | None = None

    @property
    def engine(self) -> RapidOCR:
        """惰性获取 RapidOCR 引擎实例。"""
        if self._engine is None:
            logger.info("正在初始化 RapidOCR 引擎...")
            self._engine = RapidOCR()
            logger.info("RapidOCR 引擎初始化完成")
        return self._engine

    # ── 文字识别（核心方法）──────────────────────

    def recognize(
        self,
        image: str | Path | np.ndarray,
        *,
        use_det: bool = True,
        use_cls: bool = True,
        use_rec: bool = True,
        **kwargs: Any,
    ) -> list[Any] | None:
        """对图像执行 OCR，返回识别结果列表。

        Args:
            image: 图片路径、URL 或 numpy 数组（BGR/RGB）。
            use_det: 是否启用文字检测。
            use_cls: 是否启用方向分类（竖排文本纠正）。
            use_rec: 是否启用文字识别。
            **kwargs: 透传给 RapidOCR 引擎的额外参数。

        Returns:
            识别结果列表，每项格式取决于使用的管线组合；
            典型文字识别结果: (bbox, text, score)。
            失败返回 None。
        """
        try:
            result = self.engine(
                image,
                use_det=use_det,
                use_cls=use_cls,
                use_rec=use_rec,
                **kwargs,
            )
            return result
        except Exception:
            logger.exception("OCR 识别失败")
            return None

    # ── 便捷方法 ──────────────────────────────

    def recognize_text_only(
        self, image: str | Path | np.ndarray, **kwargs: Any,
    ) -> list[str]:
        """仅识别文字内容，返回文本列表。

        Args:
            image: 图片路径、URL 或 numpy 数组。
            **kwargs: 透传给引擎的额外参数。

        Returns:
            识别到的文本字符串列表；失败返回空列表。
        """
        result = self.recognize(image, use_det=True, use_cls=True, use_rec=True, **kwargs)
        if not result:
            return []
        # result 格式: [(bbox, text, score), ...]
        return [item[1] for item in result if item[1]]

    def detect_text_boxes(
        self, image: str | Path | np.ndarray, **kwargs: Any,
    ) -> list[Any]:
        """仅检测文字区域边界框，不识别内容。

        Args:
            image: 图片路径、URL 或 numpy 数组。
            **kwargs: 透传给引擎的额外参数。

        Returns:
            检测到的文字区域列表；失败返回空列表。
        """
        result = self.recognize(image, use_det=True, use_cls=False, use_rec=False, **kwargs)
        return result if result else []


# ── 单例 ──────────────────────────────────────────────

_ocr_service: OcrService | None = None


def get_ocr_service() -> OcrService:
    """获取 OcrService 线程安全单例。"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OcrService()
    return _ocr_service