"""核心配置模块 — 基于 pydantic-settings 统一管理所有配置项。"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 服务 ──────────────────────────────
    APP_TITLE: str = "FastAPI Template"
    APP_VERSION: str = "0.1.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # ── 工程目录 ──────────────────────────
    PROJECTS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "projects"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
