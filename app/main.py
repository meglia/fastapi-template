"""FastAPI 应用入口 — 集成 REST API、AI 推理服务与私有网络协议。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.config import settings
from app.protocols.manager import protocol_manager
from app.protocols.implementations.sample_protocol import SampleProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── lifespan: 统一管理 HTTP 服务与私有协议生命周期 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 注册私有协议（按需在此注册更多协议）
    protocol_manager.register(SampleProtocol())

    # 启动所有私有协议
    await protocol_manager.start_all()
    logger.info("所有私有协议已启动")

    yield  # 应用运行中...

    # 关闭
    await protocol_manager.stop_all()
    logger.info("所有私有协议已停止")


app = FastAPI(
    title="HMSB AI Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# ── 中间件 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──
app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": "HMSB AI Platform", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}