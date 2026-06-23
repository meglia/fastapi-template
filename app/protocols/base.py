"""私有协议抽象基类 — 所有协议实现必须继承此基类。

本模块定义协议配置、连接状态、报文消息等数据类，以及同步非 async 的
BaseProtocol 抽象基类。所有协议实现运行在独立子进程中，使用同步阻塞 I/O。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ═══════════════════════════════════════════════════════════════════
#  数据类
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProtocolConfig:
    """协议连接配置。"""
    host: str = "192.168.86.166"
    port: int = 4042
    protocol_type: str = "lrkcapture"
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "protocol_type": self.protocol_type,
            "extra": self.extra,
        }


class ConnectionStatus(Enum):
    """连接状态枚举。"""
    DISCONNECTED = auto()
    CONNECTING   = auto()
    CONNECTED    = auto()
    ERROR        = auto()


@dataclass
class ProtocolMessage:
    """单条报文日志。"""
    timestamp: float = field(default_factory=time.time)
    direction: str = ""   # "send" | "recv"
    content: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "content": self.content,
            "extra": self.extra,
        }


# ═══════════════════════════════════════════════════════════════════
#  抽象基类
# ═══════════════════════════════════════════════════════════════════

class BaseProtocol(ABC):
    """私有协议抽象基类（同步版本，运行在子进程中）。

    子类需实现 connect / disconnect / send 等核心方法。
    报文日志通过 _log_message() 统一记录到内部环形缓冲区。
    """

    # 最大报文缓存条数
    MAX_MESSAGES: int = 500

    # 协议标识名（子类覆盖）
    name: str = "base"

    def __init__(self) -> None:
        self._config: ProtocolConfig = ProtocolConfig()
        self._status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._status_message: str = ""
        self._messages: deque[ProtocolMessage] = deque(maxlen=self.MAX_MESSAGES)

    # ── 配置 ──────────────────────────────────────────────────

    def configure(self, config: ProtocolConfig) -> None:
        """更新连接参数（断开状态下才允许）。"""
        self._config = config

    def get_config(self) -> ProtocolConfig:
        return self._config

    # ── 生命周期 ──────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """建立连接（阻塞调用，子类负责设置 _status）。"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接（阻塞调用，子类负责设置 _status）。"""
        ...

    def send(self, data: bytes) -> None:
        """发送原始数据（可选实现，默认抛出 NotImplementedError）。"""
        raise NotImplementedError(f"{self.name} 不支持 send 操作")

    # ── 状态 ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        """返回当前状态摘要。"""
        return {
            "name": self.name,
            "status": self._status.name,
            "status_message": self._status_message,
            "config": self._config.as_dict(),
        }

    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    # ── 报文日志 ──────────────────────────────────────────────

    def _log_message(self, direction: str, content: str, **extra: Any) -> None:
        """子类调用此方法记录收发报文。"""
        msg = ProtocolMessage(
            timestamp=time.time(),
            direction=direction,
            content=content,
            extra=extra,
        )
        self._messages.append(msg)

    def get_messages(self, since: float = 0.0) -> list[dict]:
        """返回 since 时间戳之后的新报文。"""
        return [m.as_dict() for m in self._messages if m.timestamp > since]
