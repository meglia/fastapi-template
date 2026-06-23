"""v1 版本路由聚合。"""

from fastapi import APIRouter

from app.api.v1.yolo import router as yolo_router
from app.api.v1.ocr import router as ocr_router

router = APIRouter(prefix="/v1")
router.include_router(yolo_router)
router.include_router(ocr_router)
