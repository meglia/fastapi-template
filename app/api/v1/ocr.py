"""PaddleOCR 文字识别 API 端点。"""

import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.services.ocr_service import ocr_service
from app.schemas.ocr import OCRResponse

router = APIRouter(prefix="/ocr", tags=["OCR 文字识别"])


@router.post("/recognize", response_model=OCRResponse)
async def recognize_text(file: UploadFile = File(...)) -> OCRResponse:
    """上传图片进行文字识别。"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "仅支持图片文件")

    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "无法解码图片")

    return ocr_service.predict(image, filename=file.filename or "unknown")
