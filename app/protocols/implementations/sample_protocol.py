"""示例私有协议 — 演示如何基于 BaseProtocol 实现自定义 TCP/二进制协议。

实际项目可按此模板扩展：binary_protocol.py, json_protocol.py 等。
"""

import asyncio
import logging

from app.protocols.base import BaseProtocol
from app.core.config import settings

logger = logging.getLogger(__name__)


class SampleProtocol(BaseProtocol):
    """示例 TCP 协议 — 监听连接并回显数据。"""

    name = "sample_tcp"

    def __init__(self, host: str = "0.0.0.0", port: int | None = None) -> None:
        self._host = host
        self._port = port or settings.PROTOCOL_TCP_PORT
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        """启动 TCP echo 服务。"""
        self._server = await asyncio.start_server(
            self._handle_client,
            self._host,
            self._port,
        )
        logger.info("SampleProtocol 监听 %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """关闭服务。"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("SampleProtocol 已关闭")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """处理客户端连接 — 回显数据。"""
        addr = writer.get_extra_info("peername")
        logger.info("新连接: %s", addr)
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                # 自定义协议逻辑在此处理
                writer.write(data)  # echo
                await writer.drain()
        except Exception:
            logger.exception("连接异常: %s", addr)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info("连接关闭: %s", addr)
