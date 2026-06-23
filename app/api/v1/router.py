"""v1 版本路由聚合。"""

from fastapi import APIRouter
from app.api.v1.endpoints.project import router as project_router
from app.api.v1.endpoints.acceptance import router as acceptance_router

router = APIRouter()
router.include_router(project_router, prefix="/projects", tags=["工程管理"])
router.include_router(acceptance_router, prefix="/projects", tags=["验收表管理"])
