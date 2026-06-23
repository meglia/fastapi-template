"""视频设备数据模型 — 设备枚举、连接控制、状态查询的请求与响应。"""

from pydantic import BaseModel, Field


class VideoDevice(BaseModel):
    """视频设备信息。"""
    device_index: int = Field(..., description="OpenCV 设备索引号")
    device_name: str = Field(..., description="设备显示名称")


class DeviceListResponse(BaseModel):
    """设备列表响应。"""
    devices: list[VideoDevice]


class ConnectRequest(BaseModel):
    """连接请求 — 指定要激活的设备索引。"""
    device_index: int = Field(..., description="要连接的设备索引")


class VideoStatus(BaseModel):
    """当前视频连接状态。"""
    connected: bool = False
    active_device: VideoDevice | None = None
    resolution: dict[str, int] = Field(default_factory=lambda: {"width": 0, "height": 0})
