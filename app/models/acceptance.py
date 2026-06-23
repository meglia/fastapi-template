"""验收表数据模型 — 上传/预览/保存的请求与响应。"""

from pydantic import BaseModel, Field


class WorkbookInfo(BaseModel):
    """单个工作簿信息。"""
    name: str
    columns: list[str]


class UploadResponse(BaseModel):
    """上传文件响应。"""
    workbooks: list[WorkbookInfo]
    file_name: str


class PreviewRequest(BaseModel):
    """预览请求 — 指定工作簿和列映射。"""
    workbook: str = Field(..., description="工作簿名称")
    point_column: str = Field(..., description="点号列名")
    desc_column: str = Field(..., description="描述列名")


class AcceptanceRow(BaseModel):
    """
    验收表单行数据 — 完整业务字段。
    导入时仅填充 point_number / description，其余字段在验收流程中逐步填写。
    """
    point_number: str = ""
    description: str = ""
    old_backend_object: str = ""
    old_backend_screenshot: str = ""
    old_backend_recognition: str = ""
    new_backend_object: str = ""
    new_backend_screenshot: str = ""
    new_backend_recognition: str = ""
    acceptance_status: str = "待验收"
    acceptance_time: str = ""


class PreviewResponse(BaseModel):
    """预览响应。"""
    rows: list[AcceptanceRow]
    total_count: int


class SaveRequest(BaseModel):
    """保存请求 — 同预览请求，执行持久化。"""
    workbook: str = Field(..., description="工作簿名称")
    point_column: str = Field(..., description="点号列名")
    desc_column: str = Field(..., description="描述列名")


class SaveResponse(BaseModel):
    """保存响应。"""
    message: str
    file_path: str
    total_count: int


class AcceptanceData(BaseModel):
    """获取已保存验收表数据的响应。"""
    exists: bool = False
    file_name: str | None = None
    items: list[AcceptanceRow] | None = None
