"""私有协议抽象基类 — 所有协议实现必须继承此基类。"""

from abc import ABC, abstractmethod
import asyncio


class BaseProtocol(ABC):
    """私有协议抽象基类。

    子类需实现 start / stop，并可覆盖 name 属性用于注册标识。
    """

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """启动协议服务（非阻塞，内部应创建后台任务）。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """优雅关闭协议服务。"""
        ...
