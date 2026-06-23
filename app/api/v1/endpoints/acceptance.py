"""验收表管理 API — 上传/预览/保存验收表 Excel 文件。"""

import hashlib
import json
import logging
import shutil
import time as time_module
import tomllib
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response

from app.core.config import settings
from app.models.acceptance import (
    AcceptanceData,
    AcceptanceRow,
    LLMConfig,
    LocalVisionConfig,
    PreviewRequest,
    PreviewResponse,
    RecognitionConfig,
    RecordRemoteRequest,
    RecordRemoteResponse,
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
    """将文件名写入 config.toml（保留已有 created_time / description 字段以及 recognition 节）。"""
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

    # 保留已有 recognition 节
    recognition = config.get("recognition", {})
    if recognition:
        lines.append("")
        lines.extend(_format_recognition_toml(recognition))
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_recognition_toml(rec: dict) -> list[str]:
    """将 recognition 字典格式化为 TOML 行列表。"""
    lines = ["[recognition]"]
    lines.append(f'method = "{rec.get("method", "llm")}"')
    lines.append(f"region_enabled = {str(rec.get('region_enabled', False)).lower()}")
    lines.append(f"region_x = {rec.get('region_x', 0.0)}")
    lines.append(f"region_y = {rec.get('region_y', 0.0)}")
    lines.append(f"region_width = {rec.get('region_width', 1.0)}")
    lines.append(f"region_height = {rec.get('region_height', 1.0)}")

    llm = rec.get("llm", {})
    if isinstance(llm, dict):
        lines.append("")
        lines.append("[recognition.llm]")
        lines.append(f'api_url = "{llm.get("api_url", "")}"')
        lines.append(f'model_name = "{llm.get("model_name", "")}"')
        lines.append(f'api_key = "{llm.get("api_key", "")}"')

    lv = rec.get("local_vision", {})
    if isinstance(lv, dict):
        lines.append("")
        lines.append("[recognition.local_vision]")
        lines.append(f'model_path = "{lv.get("model_path", "")}"')
        lines.append(f"confidence_threshold = {lv.get('confidence_threshold', 0.5)}")

    return lines


def _load_recognition_config(project_path: Path) -> RecognitionConfig:
    """从 config.toml 加载识别配置，无配置时返回默认值。"""
    config_path = project_path / "config.toml"
    if not config_path.is_file():
        return RecognitionConfig()
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        rec = config.get("recognition", {})
        if not rec:
            return RecognitionConfig()
        return RecognitionConfig(
            method=rec.get("method", "llm"),
            region_enabled=rec.get("region_enabled", False),
            region_x=rec.get("region_x", 0.0),
            region_y=rec.get("region_y", 0.0),
            region_width=rec.get("region_width", 1.0),
            region_height=rec.get("region_height", 1.0),
            llm=LLMConfig(**rec.get("llm", {})),
            local_vision=LocalVisionConfig(**rec.get("local_vision", {})),
        )
    except Exception:
        return RecognitionConfig()


def _save_recognition_config(project_path: Path, body: RecognitionConfig):
    """将识别配置保存到 config.toml（合并已有字段）。"""
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
    fn = config.get("file_name", "")

    recognition_dict = body.model_dump()

    lines = [
        "# 工程配置文件",
        f'created_time = "{created_time}"',
        f'description = "{description}"',
    ]
    if fn:
        lines.append(f'file_name = "{fn}"')
    lines.append("")
    lines.extend(_format_recognition_toml(recognition_dict))
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


# ── 遥控验收记录 ──────────────────────────────────────────


def _serialize_signal(signal: dict) -> str:
    """将遥控信号字典序列化为可读文本，写入验收表遥控对象列。"""
    desc = signal.get("description", "")
    path = signal.get("path", "")
    state_label = signal.get("state_label", "")
    state = signal.get("state")
    ts_str = signal.get("signal_ts_str", "")
    parts = [
        f"desc={desc}",
        f"path={path}",
        f"state={state_label}",
    ]
    if state is not None:
        parts.append(f"state_raw=0x{state:02X}")
    if ts_str:
        parts.append(f"ts={ts_str}")
    return " | ".join(parts)


def _save_screenshot(project_path: Path, frame) -> str:
    """在原始帧左下角打时标，编码为 JPEG 并保存到 screenshots/ 目录，返回文件名。

    frame: numpy ndarray (BGR)，来自 VideoService.get_raw_frame()
    """
    import cv2
    import datetime

    screenshots_dir = project_path / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # 打时标 — 左下角白色文字 + 黑色半透明背景条
    now = datetime.datetime.now()
    ts_text = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.6, w / 1280.0)
    thickness = max(1, int(w / 640))
    (tw, th), baseline = cv2.getTextSize(ts_text, font, font_scale, thickness)
    # 背景条
    margin = 8
    bar_y1 = h - th - baseline - margin * 2
    bar_y2 = h - margin
    bar_x1 = margin
    bar_x2 = margin + tw + margin * 2
    overlay = frame.copy()
    cv2.rectangle(overlay, (bar_x1, bar_y1), (bar_x2, bar_y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    # 白色文字
    text_x = margin + margin
    text_y = h - margin - baseline
    cv2.putText(frame, ts_text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    # 编码为 JPEG
    success, jpeg = cv2.imencode('.jpg', frame)
    if not success:
        raise RuntimeError("JPEG 编码失败")
    jpeg_bytes = jpeg.tobytes()

    file_hash = hashlib.sha256(jpeg_bytes).hexdigest()[:16]
    ts_int = int(time_module.time() * 1000)
    filename = f"{file_hash}_{ts_int}.jpg"
    filepath = screenshots_dir / filename
    filepath.write_bytes(jpeg_bytes)
    logger.info("截图已保存(含时标): %s (%d bytes)", filename, len(jpeg_bytes))
    return filename


@router.post("/{project_name}/acceptance/record-remote", response_model=RecordRemoteResponse)
async def record_remote_acceptance(project_name: str, body: RecordRemoteRequest):
    """收到遥控报文时记录验收数据。

    根据 backend_type (old/new) 决定写入老后台还是新后台列；
    同时截取当前视频画面保存为截图；
    row_indices 指定勾选行，为 None 时自动找第一个空行填充。
    """
    project_path = _get_project_path(project_name)

    # 校验 backend_type
    if body.backend_type not in ("old", "new"):
        raise HTTPException(status_code=400, detail="backend_type 必须为 old 或 new")

    # 读取已有验收数据
    data_path = project_path / DATA_FILE_NAME
    if not data_path.is_file():
        raise HTTPException(status_code=400, detail="请先导入并保存验收表")

    try:
        items_raw = json.loads(data_path.read_text(encoding="utf-8"))
        rows = [AcceptanceRow(**item) for item in items_raw]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取验收数据失败: {e}")

    # 截图
    screenshot_filename = ""
    try:
        from app.services.video_service import get_video_service
        vs = get_video_service()
        raw_frame = vs.get_raw_frame()
        if raw_frame is not None:
            screenshot_filename = _save_screenshot(project_path, raw_frame)
        else:
            logger.warning("[遥控验收] 视频服务无帧可截")
    except Exception as e:
        logger.warning("[遥控验收] 截图失败: %s", e)

    # 序列化信号文本
    signal_text = _serialize_signal(body.signal)

    # 确定需要填充的行索引
    is_old = body.backend_type == "old"
    obj_field = "old_backend_object" if is_old else "new_backend_object"
    ss_field = "old_backend_screenshot" if is_old else "new_backend_screenshot"

    filled_indices: list[int] = []

    if body.row_indices is not None and len(body.row_indices) > 0:
        # 填充勾选行
        for idx in body.row_indices:
            if 0 <= idx < len(rows):
                setattr(rows[idx], obj_field, signal_text)
                if screenshot_filename:
                    setattr(rows[idx], ss_field, screenshot_filename)
                filled_indices.append(idx)
    else:
        # 自动找第一个空行
        for idx, row in enumerate(rows):
            current_val = getattr(row, obj_field, "")
            if not current_val:
                setattr(row, obj_field, signal_text)
                if screenshot_filename:
                    setattr(row, ss_field, screenshot_filename)
                filled_indices.append(idx)
                break

    if not filled_indices:
        raise HTTPException(status_code=400, detail=f"{'老后台' if is_old else '新后台'}遥控对象列已全部填满，无可填充的空行")

    # 写回 JSON
    data_json = [r.model_dump() for r in rows]
    data_path.write_text(json.dumps(data_json, ensure_ascii=False, indent=2), encoding="utf-8")

    log_msg = (
        f"[遥控验收] 后台={'老' if is_old else '新'} "
        f"信号={signal_text[:80]} "
        f"截图={screenshot_filename or '无'} "
        f"填充行={filled_indices}"
    )
    logger.info(log_msg)

    return RecordRemoteResponse(rows=rows, filled_indices=filled_indices)


@router.get("/{project_name}/acceptance/screenshot/{filename}")
async def get_screenshot(project_name: str, filename: str):
    """获取验收截图文件。"""
    project_path = _get_project_path(project_name)
    file_path = project_path / "screenshots" / filename

    # 安全检查：防止路径穿越
    resolved = file_path.resolve()
    allowed_base = (project_path / "screenshots").resolve()
    if not str(resolved).startswith(str(allowed_base)):
        raise HTTPException(status_code=403, detail="禁止访问")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="截图文件不存在")

    content = resolved.read_bytes()
    return Response(content=content, media_type="image/jpeg")


# ── 识别配置端点 ──────────────────────────────────────────

@router.get("/{project_name}/recognition-config", response_model=RecognitionConfig)
async def get_recognition_config(project_name: str):
    """获取工程的识别配置（识别方式、区域、模型参数等）。"""
    project_path = _get_project_path(project_name)
    return _load_recognition_config(project_path)


@router.put("/{project_name}/recognition-config", response_model=RecognitionConfig)
async def save_recognition_config(project_name: str, body: RecognitionConfig):
    """保存工程的识别配置到 config.toml。"""
    project_path = _get_project_path(project_name)
    _save_recognition_config(project_path, body)
    logger.info("识别配置已保存: project=%s, method=%s", project_name, body.method)
    return body
