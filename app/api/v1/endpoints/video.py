"""视频管理 API — 设备枚举、连接控制与实时帧获取。"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.video import (
    ConnectRequest,
    DeviceListResponse,
    VideoStatus,
)
from app.services.video_service import get_video_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices():
    """枚举当前系统所有可用的视频设备。"""
    service = get_video_service()
    devices = service.get_devices()
    return DeviceListResponse(devices=devices)


@router.post("/connect")
async def connect_device(body: ConnectRequest):
    """激活指定视频设备，开始采集画面。"""
    service = get_video_service()
    try:
        service.connect(body.device_index)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "连接成功", "device_index": body.device_index}


@router.post("/disconnect")
async def disconnect_device():
    """断开当前视频设备连接。"""
    service = get_video_service()
    service.disconnect()
    return {"message": "已断开连接"}


@router.get("/status", response_model=VideoStatus)
async def get_status():
    """获取当前视频连接状态。"""
    service = get_video_service()
    return service.get_status()


@router.get("/frame")
async def get_frame():
    """获取实时视频帧（JPEG 格式）。

    返回当前最新一帧的 JPEG 图像，未连接或无帧时返回 503。
    """
    service = get_video_service()
    if not service.get_status().connected:
        raise HTTPException(status_code=503, detail="视频设备未连接")

    jpeg_bytes = service.get_frame()
    if jpeg_bytes is None:
        raise HTTPException(status_code=503, detail="暂无视频帧")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
