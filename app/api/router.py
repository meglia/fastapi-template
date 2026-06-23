"""API 总路由 — 聚合所有版本。"""

from fastapi import APIRouter
from app.api.v1.router import router as v1_router

router = APIRouter(prefix="/api")
router.include_router(v1_router, prefix="/v1")

