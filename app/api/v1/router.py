"""v1 版本路由聚合。"""

from fastapi import APIRouter
from app.api.v1.endpoints.project import router as project_router

router = APIRouter()
router.include_router(project_router, prefix="/projects", tags=["工程管理"])
