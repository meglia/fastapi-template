"""核心配置模块 — 基于 pydantic-settings 统一管理所有配置项。"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 服务 ──────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # ── YOLO 模型 ─────────────────────────
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    YOLO_CONF_THRESHOLD: float = 0.5
    YOLO_IOU_THRESHOLD: float = 0.45

    # ── PaddleOCR ─────────────────────────
    OCR_USE_GPU: bool = False
    OCR_LANG: str = "ch"
    OCR_DET_MODEL_DIR: str | None = None
    OCR_REC_MODEL_DIR: str | None = None

    # ── 上传限制 ──────────────────────────
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── 私有协议 ──────────────────────────
    PROTOCOL_TCP_PORT: int = 9000
    PROTOCOL_UDP_PORT: int = 9001

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
