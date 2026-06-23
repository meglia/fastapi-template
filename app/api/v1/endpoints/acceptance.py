"""验收表管理 API — 上传/预览/保存验收表 Excel 文件。"""

import json
import logging
import shutil
import tomllib
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.core.config import settings
from app.models.acceptance import (
    AcceptanceData,
    AcceptanceRow,
    PreviewRequest,
    PreviewResponse,
    SaveRequest,
    SaveResponse,
    UploadResponse,
    WorkbookInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 常量 ──────────────────────────────────────────────────
TEMP_FILE_PREFIX = ".temp_acceptance_upload"
TEMP_ORIGINAL_NAME_FILE = ".temp_original_name.txt"
DATA_FILE_NAME = "acceptance_data.json"


# ── 工具函数 ──────────────────────────────────────────────


def _get_project_path(project_name: str) -> Path:
    """获取工程目录路径，不存在则抛出 404。"""
    project_path = settings.PROJECTS_DIR / project_name
    if not project_path.is_dir():
        raise HTTPException(status_code=404, detail=f"工程 '{project_name}' 不存在")
    return project_path


def _find_temp_file(project_path: Path) -> tuple[Path | None, str]:
    """在工程目录中查找临时上传文件，返回 (路径, 扩展名)。"""
    for ext in (".xlsx", ".xls"):
        for candidate in project_path.glob(f"{TEMP_FILE_PREFIX}*{ext}"):
            return candidate, ext
    return None, ""


def _read_excel_workbooks(file_path: Path) -> list[WorkbookInfo]:
    """读取 Excel 文件的所有工作簿名称和列名。"""
    engine = "openpyxl" if file_path.suffix.lower() == ".xlsx" else "xlrd"
    xl = pd.ExcelFile(file_path, engine=engine)
    workbooks = []
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name, nrows=0)
        columns = [str(c) for c in df.columns.tolist()]
        workbooks.append(WorkbookInfo(name=sheet_name, columns=columns))
    xl.close()
    return workbooks


def _parse_rows(file_path: Path, workbook: str, point_col: str, desc_col: str) -> list[AcceptanceRow]:
    """解析 Excel 中指定工作簿和列的数据，返回 AcceptanceRow 列表（仅填充点号/描述）。"""
    engine = "openpyxl" if file_path.suffix.lower() == ".xlsx" else "xlrd"
    df = pd.read_excel(file_path, sheet_name=workbook, engine=engine)
    df.columns = [str(c) for c in df.columns]

    if point_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"列 '{point_col}' 在当前工作簿中不存在")
    if desc_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"列 '{desc_col}' 在当前工作簿中不存在")

    sub = df[[point_col, desc_col]].dropna(how="all")
    rows = []
    for _, row in sub.iterrows():
        rows.append(AcceptanceRow(
            point_number=str(row[point_col]) if pd.notna(row[point_col]) else "",
            description=str(row[desc_col]) if pd.notna(row[desc_col]) else "",
        ))
    return rows


def _load_existing_data(project_path: Path) -> dict[str, AcceptanceRow]:
    """读取已保存的验收表数据，按点号索引，用于重新导入时保留验收进度。"""
    data_path = project_path / DATA_FILE_NAME
    if not data_path.is_file():
        return {}
    try:
        items = json.loads(data_path.read_text(encoding="utf-8"))
        return {item["point_number"]: AcceptanceRow(**item) for item in items}
    except Exception:
        return {}


def _cleanup_old_temp(project_path: Path):
    """清理工程目录下所有旧临时文件。"""
    for p in project_path.glob(f"{TEMP_FILE_PREFIX}*"):
        try:
            p.unlink()
        except Exception:
            pass
    name_file = project_path / TEMP_ORIGINAL_NAME_FILE
    if name_file.is_file():
        try:
            name_file.unlink()
        except Exception:
            pass


def _write_config_toml(project_path: Path, *, file_name: str | None = None):
    """将文件名写入 config.toml（保留已有 created_time / description 字段）。"""
    config_path = project_path / "config.toml"
    config = {}
    if config_path.is_file():
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
        except Exception:
            pass

    created_time = config.get("created_time", "")
    description = config.get("description", "")
    # 若未传入 file_name，保留已有值
    fn = file_name if file_name is not None else config.get("file_name", "")

    lines = [
        "# 工程配置文件",
        f'created_time = "{created_time}"',
        f'description = "{description}"',
    ]
    if fn:
        lines.append(f'file_name = "{fn}"')
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── API 端点 ──────────────────────────────────────────────


@router.post("/{project_name}/acceptance/upload", response_model=UploadResponse)
async def upload_acceptance(project_name: str, file: UploadFile = File(...)):
    """上传验收表 Excel 文件（.xls / .xlsx），返回所有工作簿及列名。"""
    project_path = _get_project_path(project_name)

    # 校验文件扩展名
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xls 或 .xlsx 格式的 Excel 文件")

    # 清理旧临时文件，写入新临时文件
    _cleanup_old_temp(project_path)
    temp_path = project_path / f"{TEMP_FILE_PREFIX}{ext}"
    content = await file.read()
    temp_path.write_bytes(content)

    # 记录原始文件名，供保存时使用
    (project_path / TEMP_ORIGINAL_NAME_FILE).write_text(original_name, encoding="utf-8")

    try:
        workbooks = _read_excel_workbooks(temp_path)
    except Exception as e:
        logger.error("读取 Excel 失败: %s", e)
        # 清理无效临时文件
        try:
            temp_path.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"无法解析 Excel 文件: {e}")

    logger.info("上传验收表: project=%s, file=%s, sheets=%d",
                project_name, original_name, len(workbooks))
    return UploadResponse(workbooks=workbooks, file_name=original_name)


@router.post("/{project_name}/acceptance/preview", response_model=PreviewResponse)
async def preview_acceptance(project_name: str, body: PreviewRequest):
    """根据选择的工作簿与列映射，预览解析后的验收表数据。"""
    project_path = _get_project_path(project_name)
    temp_path, _ = _find_temp_file(project_path)
    if temp_path is None:
        raise HTTPException(status_code=400, detail="请先上传验收表文件")

    try:
        rows = _parse_rows(temp_path, body.workbook, body.point_column, body.desc_column)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("预览验收表失败: %s", e)
        raise HTTPException(status_code=400, detail=f"预览失败: {e}")

    return PreviewResponse(rows=rows, total_count=len(rows))


@router.post("/{project_name}/acceptance/save", response_model=SaveResponse)
async def save_acceptance(project_name: str, body: SaveRequest):
    """保存验收表：将临时文件持久化到工程文件夹，同时导出解析后的 JSON。
    重新导入时按点号合并已有验收进度，保留已填写的业务字段。"""
    project_path = _get_project_path(project_name)
    temp_path, temp_ext = _find_temp_file(project_path)
    if temp_path is None:
        raise HTTPException(status_code=400, detail="请先上传验收表文件")

    try:
        rows = _parse_rows(temp_path, body.workbook, body.point_column, body.desc_column)
        # 合并已有验收进度：按点号匹配，保留已填写的验收字段
        existing = _load_existing_data(project_path)
        for r in rows:
            old = existing.get(r.point_number)
            if old is not None:
                r.old_backend_object = old.old_backend_object
                r.old_backend_screenshot = old.old_backend_screenshot
                r.old_backend_recognition = old.old_backend_recognition
                r.new_backend_object = old.new_backend_object
                r.new_backend_screenshot = old.new_backend_screenshot
                r.new_backend_recognition = old.new_backend_recognition
                r.acceptance_status = old.acceptance_status
                r.acceptance_time = old.acceptance_time
    except HTTPException:
        raise
    except Exception as e:
        logger.error("保存验收表时解析失败: %s", e)
        raise HTTPException(status_code=400, detail=f"解析失败: {e}")

    # 读取上传时记录的原始文件名
    original_name_file = project_path / TEMP_ORIGINAL_NAME_FILE
    original_name = temp_ext  # fallback
    if original_name_file.is_file():
        try:
            original_name = original_name_file.read_text(encoding="utf-8").strip() or temp_ext
        except Exception:
            pass

    # 删除已有最终文件（查找工程目录下非临时 Excel 文件）
    for ext in (".xlsx", ".xls"):
        for old in project_path.glob(f"*.{ext[1:]}"):
            if not old.name.startswith(TEMP_FILE_PREFIX):
                try:
                    old.unlink()
                except Exception:
                    pass

    # 使用原始文件名（保留扩展名一致性）
    final_name = Path(original_name).stem + temp_ext
    final_path = project_path / final_name
    shutil.move(str(temp_path), str(final_path))

    # 同步更新 config.toml 中的文件名
    _write_config_toml(project_path, file_name=final_name)

    # 清理临时原始文件名记录
    if original_name_file.is_file():
        try:
            original_name_file.unlink()
        except Exception:
            pass

    # 写入解析后的 JSON 数据
    data_path = project_path / DATA_FILE_NAME
    data_json = [r.model_dump() for r in rows]
    data_path.write_text(json.dumps(data_json, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("保存验收表: project=%s, file=%s, rows=%d",
                project_name, final_path.name, len(rows))
    return SaveResponse(
        message="验收表保存成功",
        file_path=str(final_path.absolute()),
        total_count=len(rows),
    )


@router.get("/{project_name}/acceptance", response_model=AcceptanceData)
async def get_acceptance(project_name: str):
    """获取已保存的验收表数据（JSON 格式）。"""
    project_path = _get_project_path(project_name)
    data_path = project_path / DATA_FILE_NAME

    if not data_path.is_file():
        return AcceptanceData(exists=False)

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        # 从 config.toml 读取文件名，回退到文件系统搜索
        file_name = None
        try:
            config_path = project_path / "config.toml"
            if config_path.is_file():
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
                file_name = config.get("file_name")
        except Exception:
            pass
        if file_name is None:
            for ext in (".xlsx", ".xls"):
                for f in project_path.glob(f"*.{ext[1:]}"):
                    if not f.name.startswith(TEMP_FILE_PREFIX):
                        file_name = f.name
                        break
                if file_name:
                    break
        return AcceptanceData(
            exists=True,
            file_name=file_name,
            items=[AcceptanceRow(**item) for item in data],
        )
    except Exception as e:
        logger.error("读取验收表数据失败: %s", e)
        return AcceptanceData(exists=False)
