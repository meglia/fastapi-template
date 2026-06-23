"""YOLO 目标检测 API 端点。"""

import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.services.yolo_service import yolo_service
from app.schemas.yolo import YoloResponse

router = APIRouter(prefix="/yolo", tags=["YOLO 目标检测"])


@router.post("/detect", response_model=YoloResponse)
async def detect_objects(file: UploadFile = File(...)) -> YoloResponse:
    """上传图片进行目标检测。"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "仅支持图片文件")

    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "无法解码图片")

    return yolo_service.predict(image, filename=file.filename or "unknown")
