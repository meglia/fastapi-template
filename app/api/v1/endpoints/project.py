"""工程管理 API — 扫描/创建/重命名/删除 projects 目录下的工程。"""

import logging
import shutil
import tomllib
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.models.project import (
    ProjectCreate,
    ProjectRename,
    ProjectUpdate,
    ProjectResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 工具函数 ──────────────────────────────────────────────


def _read_config_toml(project_path: Path) -> dict | None:
    """读取工程目录下的 config.toml，返回解析后的字典或 None。"""
    toml_path = project_path / "config.toml"
    if not toml_path.is_file():
        return None
    try:
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def _ensure_projects_dir() -> Path:
    """确保 projects 根目录存在。"""
    settings.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return settings.PROJECTS_DIR


def _list_projects() -> list[dict]:
    """扫描 projects 目录，返回包含创建日期的工程信息列表。"""
    projects: list[dict] = []
    root = _ensure_projects_dir()
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        config = _read_config_toml(entry)
        if config is None or "created_date" not in config:
            continue
        try:
            created_date = date.fromisoformat(config["created_date"])
        except (ValueError, TypeError):
            created_date = None
        projects.append({
            "name": entry.name,
            "description": config.get("description", ""),
            "created_date": created_date,
            "path": str(entry.absolute()),
        })
    return projects


# ── API 端点 ──────────────────────────────────────────────


@router.get("", response_model=list[ProjectResponse])
async def list_projects():
    """获取所有工程列表（仅返回含 created_date 的有效工程）。"""
    return _list_projects()


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate):
    """创建新工程（自动生成 config.toml 含创建日期）。"""
    root = _ensure_projects_dir()
    project_path = root / body.name
    if project_path.exists():
        raise HTTPException(status_code=409, detail=f"工程 '{body.name}' 已存在")

    project_path.mkdir(parents=True)
    today = date.today().isoformat()
    toml_content = f"""# 工程配置文件
created_date = "{today}"
description = "{body.description}"
"""
    (project_path / "config.toml").write_text(toml_content, encoding="utf-8")
    logger.info("创建工程: %s", body.name)

    return ProjectResponse(
        name=body.name,
        description=body.description,
        created_date=date.today(),
        path=str(project_path.absolute()),
    )


@router.put("/{project_name}/rename", response_model=ProjectResponse)
async def rename_project(project_name: str, body: ProjectRename):
    """重命名工程（目录 + config.toml 同步更新）。"""
    root = _ensure_projects_dir()
    src = root / project_name
    if not src.is_dir():
        raise HTTPException(status_code=404, detail=f"工程 '{project_name}' 不存在")

    dst = root / body.new_name
    if dst.exists():
        raise HTTPException(status_code=409, detail=f"工程 '{body.new_name}' 已存在")

    # 重命名目录
    src.rename(dst)
    # 更新 config.toml 确保一致性（created_date 保留）
    config = _read_config_toml(dst) or {}
    created_date = config.get("created_date", date.today().isoformat())
    description = config.get("description", "")
    toml_content = f"""# 工程配置文件
created_date = "{created_date}"
description = "{description}"
"""
    (dst / "config.toml").write_text(toml_content, encoding="utf-8")
    logger.info("重命名工程: %s → %s", project_name, body.new_name)

    try:
        cd = date.fromisoformat(created_date)
    except (ValueError, TypeError):
        cd = None
    return ProjectResponse(
        name=body.new_name,
        description=description,
        created_date=cd,
        path=str(dst.absolute()),
    )


@router.put("/{project_name}", response_model=ProjectResponse)
async def update_project(project_name: str, body: ProjectUpdate):
    """更新工程描述。"""
    root = _ensure_projects_dir()
    project_path = root / project_name
    if not project_path.is_dir():
        raise HTTPException(status_code=404, detail=f"工程 '{project_name}' 不存在")

    config = _read_config_toml(project_path)
    if config is None:
        raise HTTPException(status_code=400, detail="config.toml 不可读")

    created_date = config.get("created_date", date.today().isoformat())
    toml_content = f"""# 工程配置文件
created_date = "{created_date}"
description = "{body.description}"
"""
    (project_path / "config.toml").write_text(toml_content, encoding="utf-8")
    logger.info("更新工程描述: %s", project_name)

    try:
        cd = date.fromisoformat(created_date)
    except (ValueError, TypeError):
        cd = None
    return ProjectResponse(
        name=project_name,
        description=body.description,
        created_date=cd,
        path=str(project_path.absolute()),
    )


@router.delete("/{project_name}", status_code=204)
async def delete_project(project_name: str):
    """删除工程（包括其下所有文件）。"""
    root = _ensure_projects_dir()
    project_path = root / project_name
    if not project_path.is_dir():
        raise HTTPException(status_code=404, detail=f"工程 '{project_name}' 不存在")

    shutil.rmtree(project_path)
    logger.info("删除工程: %s", project_name)
