"""FastAPI 应用入口 — 集成 REST API、AI 推理服务与私有网络协议。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.router import router as api_router
from app.core.config import settings
from app.protocols.manager import protocol_manager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── lifespan: 统一管理 HTTP 服务与私有协议生命周期 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动协议管理子进程
    logger.info("正在启动协议管理器...")
    protocol_manager.start()
    logger.info("协议管理器已启动")

    yield

    # 关闭协议管理子进程
    logger.info("正在停止协议管理器...")
    protocol_manager.stop()
    logger.info("协议管理器已停止")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
# ── 路由注册 ──
app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": settings.APP_TITLE, "version": settings.APP_VERSION}


@app.get("/health")
async def health():
    return {"status": "ok"}