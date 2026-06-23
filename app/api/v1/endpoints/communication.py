"""通讯管理 API — 协议连接启停、状态查询、报文日志。"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.protocols.manager import protocol_manager, CMD_CONNECT, CMD_DISCONNECT, CMD_STATUS, CMD_REMOTE_ONLY, CMD_CLEAR_MESSAGES

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
#  请求/响应模型
# ═══════════════════════════════════════════════════════════════════

class ConnectRequest(BaseModel):
    host: str = Field(default="192.168.86.166", description="设备 IP 地址")
    port: int = Field(default=4042, description="设备端口")
    protocol_type: str = Field(default="lrkcapture", description="协议类型")
    extra: dict[str, Any] = Field(default_factory=dict, description="额外参数（如 asdu_addr）")


class DisconnectRequest(BaseModel):
    host: str = Field(default="192.168.86.166", description="设备 IP 地址")
    port: int = Field(default=4042, description="设备端口")
    protocol_type: str = Field(default="lrkcapture", description="协议类型")


class RemoteOnlyRequest(BaseModel):
    host: str = Field(default="192.168.86.166", description="设备 IP 地址")
    port: int = Field(default=4042, description="设备端口")
    protocol_type: str = Field(default="lrkcapture", description="协议类型")
    enabled: bool = Field(default=True, description="是否只接收遥控报文")

class ClearMessagesRequest(BaseModel):
    host: str = Field(default="192.168.86.166", description="设备 IP 地址")
    port: int = Field(default=4042, description="设备端口")
    protocol_type: str = Field(default="lrkcapture", description="协议类型")


# ═══════════════════════════════════════════════════════════════════
#  API 端点（def 而非 async def，因为底层涉及阻塞跨进程通信）
# ═══════════════════════════════════════════════════════════════════

@router.post("/connect")
def connect_device(body: ConnectRequest):
    """连接设备：通过协议管理器子进程建立 TCP 连接并发送启动帧。"""
    resp = protocol_manager.send_command(
        CMD_CONNECT,
        host=body.host,
        port=body.port,
        protocol_type=body.protocol_type,
        extra=body.extra,
    )
    if resp.get("error"):
        raise HTTPException(status_code=500, detail=resp.get("error"))
    return resp


@router.post("/disconnect")
def disconnect_device(body: DisconnectRequest):
    """断开设备连接。"""
    resp = protocol_manager.send_command(
        CMD_DISCONNECT,
        host=body.host,
        port=body.port,
        protocol_type=body.protocol_type,
    )
    if resp.get("error"):
        raise HTTPException(status_code=500, detail=resp.get("error"))
    return resp


@router.get("/status")
def get_status():
    """获取当前连接状态（从主进程缓存读取，毫秒级响应）。"""
    return protocol_manager.get_status()


@router.get("/messages")
def get_messages(since: float = 0.0):
    """获取报文日志。
    
    - `since`: Unix 时间戳，只返回该时间之后的新报文（用于增量轮询）。
    """
    return protocol_manager.get_messages(since)


@router.post("/clear-messages")
def clear_messages(body: ClearMessagesRequest):
    """清空主进程及子进程的报文缓冲区。"""
    resp = protocol_manager.clear_messages(
        host=body.host,
        port=body.port,
        protocol_type=body.protocol_type,
    )
    if resp.get("error"):
        raise HTTPException(status_code=500, detail=resp.get("error"))
    return resp


@router.get("/ping")
def ping_manager():
    """检测协议管理子进程是否存活。"""
    resp = protocol_manager.send_command(CMD_STATUS)
    return {"alive": resp.get("error") is None, "detail": resp}


@router.post("/remote-only")
def set_remote_only(body: RemoteOnlyRequest):
    """设置只接收遥控报文模式。开启后子进程跳过非 0xFB 帧的日志记录，
    避免普通报文占满缓冲区挤掉遥控报文。"""
    resp = protocol_manager.send_command(
        CMD_REMOTE_ONLY,
        host=body.host,
        port=body.port,
        protocol_type=body.protocol_type,
        enabled=body.enabled,
    )
    if resp.get("error"):
        raise HTTPException(status_code=500, detail=resp.get("error"))
    return resp
