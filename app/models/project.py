"""工程数据模型 — Pydantic 校验与序列化。"""

from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """创建工程请求体。"""
    name: str = Field(..., min_length=1, max_length=128, description="工程名称")
    description: str = Field(default="", max_length=512, description="工程描述")


class ProjectRename(BaseModel):
    """重命名工程请求体。"""
    new_name: str = Field(..., min_length=1, max_length=128, description="新工程名称")


class ProjectUpdate(BaseModel):
    """更新工程描述请求体。"""
    description: str = Field(default="", max_length=512, description="工程描述")


class ProjectResponse(BaseModel):
    """工程列表响应体。"""
    name: str
    description: str
    created_time: datetime | None = None
    path: str
