"""协议管理器 — 统一管理所有私有协议的生命周期。"""

import logging
from app.protocols.base import BaseProtocol

logger = logging.getLogger(__name__)


class ProtocolManager:
    """管理多个 BaseProtocol 实例的启停。"""

    def __init__(self) -> None:
        self._protocols: dict[str, BaseProtocol] = {}

    def register(self, protocol: BaseProtocol) -> None:
        """注册一个协议实例（需在 lifespan 启动前完成）。"""
        if protocol.name in self._protocols:
            logger.warning("协议 %s 已注册，将被覆盖", protocol.name)
        self._protocols[protocol.name] = protocol
        logger.info("注册协议: %s", protocol.name)

    async def start_all(self) -> None:
        """启动所有已注册协议。"""
        for name, proto in self._protocols.items():
            logger.info("启动协议: %s", name)
            await proto.start()

    async def stop_all(self) -> None:
        """停止所有已注册协议。"""
        for name, proto in self._protocols.items():
            logger.info("停止协议: %s", name)
            await proto.stop()


# 全局单例
protocol_manager = ProtocolManager()
