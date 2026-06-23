"""协议管理器 — 多进程架构统一管理所有私有协议的生命周期。

架构：
  ProtocolManager（主进程）── command_queue ──→ ProtocolManagerProcess（子进程）
                          ←── event_queue   ──

主进程通过 command_queue 向子进程发送命令，子进程通过 event_queue
回传状态变更、报文日志和命令响应。主进程侧维护内存状态缓存和报文
环形缓冲区，API 层直接读取。
"""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
import uuid
from collections import deque
from typing import Any

from app.protocols.base import (
    BaseProtocol,
    ConnectionStatus,
    ProtocolConfig,
    ProtocolMessage,
)

logger = logging.getLogger(__name__)

# 事件队列最大容量
MAX_EVENTS: int = 2000
MAX_MESSAGES_BUFFER: int = 1000


# ═══════════════════════════════════════════════════════════════════
#  命令常量
# ═══════════════════════════════════════════════════════════════════

CMD_CONNECT    = "connect"
CMD_DISCONNECT = "disconnect"
CMD_SEND       = "send"
CMD_CONFIGURE  = "configure"
CMD_STATUS     = "status"
CMD_REMOTE_ONLY    = "remote_only"
CMD_CLEAR_MESSAGES = "clear_messages"
CMD_SHUTDOWN       = "shutdown"

EVT_STATUS     = "status"
EVT_MESSAGE    = "message"
EVT_RESPONSE   = "response"
EVT_ERROR      = "error"


# ═══════════════════════════════════════════════════════════════════
#  子进程侧：协议管理进程
# ═══════════════════════════════════════════════════════════════════

class ProtocolManagerProcess(multiprocessing.Process):
    """独立子进程 — 持有并管理所有 BaseProtocol 实例。"""

    def __init__(
        self,
        command_queue: multiprocessing.Queue,
        event_queue: multiprocessing.Queue,
    ) -> None:
        super().__init__(daemon=True, name="protocol-manager")
        self._cmd_q = command_queue
        self._evt_q = event_queue
        self._protocols: dict[str, BaseProtocol] = {}
        self._running = False
        # drain cursor：记录每个协议上次 drain 的最新报文时间戳，避免重复推送
        self._drain_cursor: dict[str, float] = {}
        # 连接健康监控：跟踪状态变化、自动重连
        self._prev_status: dict[str, str] = {}
        self._reconnect_at: dict[str, float] = {}
        self._reconnect_attempts: dict[str, int] = {}

    # ── 协议注册工厂 ──────────────────────────────────────────

    def _create_protocol(self, protocol_type: str) -> BaseProtocol | None:
        """根据协议类型字符串创建协议实例。"""
        if protocol_type == "lrkcapture":
            from app.protocols.implementations.lrkcapture_protocol import LRKCAPYUREProtocol
            return LRKCAPYUREProtocol()
        logger.error("未知协议类型: %s", protocol_type)
        return None

    def _get_or_create(self, config: ProtocolConfig) -> BaseProtocol | None:
        key = f"{config.protocol_type}:{config.host}:{config.port}"
        if key in self._protocols:
            return self._protocols[key]
        proto = self._create_protocol(config.protocol_type)
        if proto is not None:
            proto.configure(config)
            self._protocols[key] = proto
        return proto

    # ── 命令处理 ──────────────────────────────────────────────

    def _handle_command(self, cmd: dict) -> None:
        cmd_type = cmd.get("type", "")
        req_id = cmd.get("request_id", "")

        try:
            if cmd_type == CMD_CONFIGURE:
                self._handle_configure(cmd, req_id)
            elif cmd_type == CMD_CONNECT:
                self._handle_connect(cmd, req_id)
            elif cmd_type == CMD_DISCONNECT:
                self._handle_disconnect(cmd, req_id)
            elif cmd_type == CMD_SEND:
                self._handle_send(cmd, req_id)
            elif cmd_type == CMD_STATUS:
                self._handle_status(req_id)
            elif cmd_type == CMD_REMOTE_ONLY:
                self._handle_remote_only(cmd, req_id)
            elif cmd_type == CMD_CLEAR_MESSAGES:
                self._handle_clear_messages(cmd, req_id)
            elif cmd_type == CMD_SHUTDOWN:
                self._running = False
            else:
                self._emit(req_id, EVT_ERROR, {"message": f"未知命令: {cmd_type}"})
        except Exception as e:
            logger.exception("命令处理异常")
            self._emit(req_id, EVT_ERROR, {"message": str(e)})

    def _handle_configure(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
            extra=cmd.get("extra", {}),
        )
        proto = self._get_or_create(cfg)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "无法创建协议实例"})
            return
        proto.configure(cfg)
        self._emit(req_id, EVT_RESPONSE, proto.get_status())

    def _handle_connect(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
            extra=cmd.get("extra", {}),
        )
        proto = self._get_or_create(cfg)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "无法创建协议实例"})
            return

        if proto.is_connected():
            self._emit(req_id, EVT_RESPONSE, proto.get_status())
            return

        try:
            proto._status = ConnectionStatus.CONNECTING
            proto._status_message = ""
            self._emit(req_id, EVT_STATUS, proto.get_status())
            proto.connect()
            self._emit(req_id, EVT_RESPONSE, proto.get_status())
        except Exception as e:
            proto._status = ConnectionStatus.ERROR
            proto._status_message = str(e)
            self._emit(req_id, EVT_ERROR, {"message": str(e)})

    def _handle_disconnect(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
        )
        key = f"{cfg.protocol_type}:{cfg.host}:{cfg.port}"
        proto = self._protocols.get(key)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "协议实例不存在"})
            return

        try:
            proto.disconnect()
            self._emit(req_id, EVT_RESPONSE, proto.get_status())
        except Exception as e:
            self._emit(req_id, EVT_ERROR, {"message": str(e)})

    def _handle_send(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
        )
        key = f"{cfg.protocol_type}:{cfg.host}:{cfg.port}"
        proto = self._protocols.get(key)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "协议实例不存在"})
            return

        raw = cmd.get("data", b"")
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        try:
            proto.send(raw)
            self._emit(req_id, EVT_RESPONSE, {"sent": len(raw)})
        except Exception as e:
            self._emit(req_id, EVT_ERROR, {"message": str(e)})

    def _handle_remote_only(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
        )
        key = f"{cfg.protocol_type}:{cfg.host}:{cfg.port}"
        proto = self._protocols.get(key)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "协议实例不存在"})
            return
        enabled = bool(cmd.get("enabled", False))
        # LRKCAPYUREProtocol 有 set_remote_only 方法，其他协议可能有或没有
        setter = getattr(proto, "set_remote_only", None)
        if setter is not None:
            setter(enabled)
        # 发出完整协议状态（含 remote_only），确保主进程缓存正确更新
        self._emit(req_id, EVT_RESPONSE, proto.get_status())

    def _handle_clear_messages(self, cmd: dict, req_id: str) -> None:
        cfg = ProtocolConfig(
            host=cmd.get("host", "192.168.86.166"),
            port=cmd.get("port", 4042),
            protocol_type=cmd.get("protocol_type", "lrkcapture"),
        )
        key = f"{cfg.protocol_type}:{cfg.host}:{cfg.port}"
        proto = self._protocols.get(key)
        if proto is None:
            self._emit(req_id, EVT_ERROR, {"message": "协议实例不存在"})
            return
        # 清空协议实例的报文缓冲区并重置 drain 游标
        proto._messages.clear()
        self._drain_cursor.pop(key, None)
        self._emit(req_id, EVT_RESPONSE, {"cleared": True})

    def _handle_status(self, req_id: str) -> None:
        result = {}
        for key, proto in self._protocols.items():
            result[key] = proto.get_status()
            result[key]["messages"] = proto.get_messages(0.0)
        self._emit(req_id, EVT_RESPONSE, result)

    # ── 连接健康监控与自动重连 ──────────────────────────────

    def _monitor_and_reconnect(self) -> None:
        """检测连接状态变化、触发自动重连。"""
        now = time.time()
        for key, proto in list(self._protocols.items()):
            current_status = proto._status.name
            prev_status = self._prev_status.get(key)

            # 状态变化时通知主进程
            if prev_status is not None and current_status != prev_status:
                self._emit("", EVT_STATUS, proto.get_status())

            self._prev_status[key] = current_status

            # 自动重连触发：曾连接成功，现因异常断开
            if prev_status == "CONNECTED" and current_status == "ERROR":
                if key not in self._reconnect_at:
                    self._reconnect_attempts[key] = 0
                    self._reconnect_at[key] = now + 3.0
                    proto._status_message = "连接断开，3秒后自动重连..."
                    self._emit("", EVT_STATUS, proto.get_status())
                    logger.info("协议 %s 连接异常断开，3秒后自动重连", key)

            # 到了重连时间
            if key in self._reconnect_at and now >= self._reconnect_at[key]:
                self._try_reconnect(key, proto)

    def _try_reconnect(self, key: str, proto: BaseProtocol) -> None:
        """尝试重连一个协议（含指数退避）。"""
        # 用户手动断开则取消自动重连
        if proto._status == ConnectionStatus.DISCONNECTED:
            self._reconnect_at.pop(key, None)
            self._reconnect_attempts.pop(key, None)
            return

        # 已经连接成功，清理重连状态
        if proto.is_connected():
            self._reconnect_at.pop(key, None)
            self._reconnect_attempts.pop(key, None)
            return

        del self._reconnect_at[key]
        self._reconnect_attempts[key] = self._reconnect_attempts.get(key, 0) + 1
        attempt = self._reconnect_attempts[key]

        logger.info("协议 %s 第 %d 次自动重连尝试...", key, attempt)

        # 清理旧 socket / 线程
        if hasattr(proto, '_sock') and proto._sock:
            try:
                proto._sock.close()
            except OSError:
                pass
            proto._sock = None
        if hasattr(proto, '_recv_thread') and proto._recv_thread is not None:
            if proto._recv_thread.is_alive():
                proto._recv_thread.join(timeout=1.0)
            proto._recv_thread = None

        proto._status = ConnectionStatus.CONNECTING
        proto._status_message = f"正在自动重连 (第{attempt}次)..."
        self._emit("", EVT_STATUS, proto.get_status())

        try:
            proto.connect()
            # 连接成功
            self._emit("", EVT_STATUS, proto.get_status())
            self._reconnect_attempts.pop(key, None)
            logger.info("协议 %s 自动重连成功", key)
        except Exception as e:
            proto._status = ConnectionStatus.ERROR
            proto._status_message = str(e)
            self._emit("", EVT_STATUS, proto.get_status())
            # 指数退避：3s, 6s, 12s, 24s, 上限 30s
            backoff = min(3.0 * (2 ** (attempt - 1)), 30.0)
            self._reconnect_at[key] = time.time() + backoff
            logger.warning(
                "协议 %s 自动重连失败 (第%d次): %s，%.0f秒后重试",
                key, attempt, e, backoff,
            )

    # ── 消息推送 ──────────────────────────────────────────────

    def _emit(self, req_id: str, evt_type: str, payload: dict) -> None:
        try:
            self._evt_q.put({
                "request_id": req_id,
                "type": evt_type,
                "payload": payload,
                "timestamp": time.time(),
            })
        except Exception:
            pass

    def _drain_protocol_messages(self) -> None:
        """推送各协议实例上次 drain 之后的新报文到主进程。"""
        for key, proto in list(self._protocols.items()):
            since = self._drain_cursor.get(key, 0.0)
            msgs = proto.get_messages(since)
            if not msgs:
                continue
            for m in msgs:
                self._emit("", EVT_MESSAGE, {"protocol_key": key, **m})
            # 更新 cursor 为本次最新报文的时间戳，下次 drain 只取增量
            self._drain_cursor[key] = max(m["timestamp"] for m in msgs)

    # ── 主循环 ────────────────────────────────────────────────

    def run(self) -> None:
        """子进程主循环。"""
        import signal as _sig
        _sig.signal(_sig.SIGINT, _sig.SIG_IGN)

        self._running = True
        last_drain = time.time()

        while self._running:
            try:
                # 非阻塞获取命令，超时 0.3s 以便定期推送报文
                cmd = self._cmd_q.get(timeout=0.3)
                self._handle_command(cmd)
            except Exception:
                pass  # 超时或其他

            # 每 0.5s 推送一次报文 + 连接健康监控
            now = time.time()
            if now - last_drain >= 0.5:
                self._drain_protocol_messages()
                self._monitor_and_reconnect()
                last_drain = now

        # 优雅关闭
        for key, proto in list(self._protocols.items()):
            try:
                if proto.is_connected():
                    proto.disconnect()
            except Exception:
                pass
        logger.info("协议管理子进程已退出")


# ═══════════════════════════════════════════════════════════════════
#  主进程侧：协议管理器
# ═══════════════════════════════════════════════════════════════════

class ProtocolManager:
    """主进程侧协议管理器 — 与子进程通信并缓存状态/报文。"""

    def __init__(self) -> None:
        self._cmd_q: multiprocessing.Queue = multiprocessing.Queue()
        self._evt_q: multiprocessing.Queue = multiprocessing.Queue()
        self._process: ProtocolManagerProcess | None = None

        # 主进程侧缓存（由后台线程更新）
        self._lock = threading.Lock()
        self._status_cache: dict[str, dict] = {}
        self._message_buffer: deque[dict] = deque(maxlen=MAX_MESSAGES_BUFFER)
        self._pending: dict[str, threading.Event] = {}  # req_id → Event
        self._responses: dict[str, dict] = {}

        self._listener_thread: threading.Thread | None = None
        self._listener_running = False

    # ── 启停 ──────────────────────────────────────────────────

    def start(self) -> None:
        """启动协议管理子进程和事件监听线程。"""
        if self._process is not None and self._process.is_alive():
            logger.warning("协议管理子进程已在运行")
            return

        self._process = ProtocolManagerProcess(self._cmd_q, self._evt_q)
        self._process.start()

        self._listener_running = True
        self._listener_thread = threading.Thread(
            target=self._listen_events,
            daemon=True,
            name="protocol-listener",
        )
        self._listener_thread.start()
        logger.info("协议管理器已启动")

    def stop(self, timeout: float = 5.0) -> None:
        """停止协议管理子进程。"""
        if self._process is None or not self._process.is_alive():
            return

        # 发送关闭命令
        try:
            self._cmd_q.put({"type": CMD_SHUTDOWN, "request_id": ""})
        except Exception:
            pass

        # 停止监听线程
        self._listener_running = False
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=2.0)

        # 等待子进程退出
        self._process.join(timeout=timeout)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=2.0)
        logger.info("协议管理器已停止")

    # ── 事件监听 ──────────────────────────────────────────────

    def _listen_events(self) -> None:
        """后台线程：持续消费事件队列，更新缓存。"""
        while self._listener_running:
            try:
                evt = self._evt_q.get(timeout=0.5)
            except Exception:
                continue

            req_id = evt.get("request_id", "")
            evt_type = evt.get("type", "")
            payload = evt.get("payload", {})

            with self._lock:
                if evt_type == EVT_STATUS or evt_type == EVT_RESPONSE:
                    self._merge_status(payload)

                if evt_type == EVT_MESSAGE:
                    self._message_buffer.append(payload)

                # 命令响应通知
                if req_id and req_id in self._pending:
                    self._responses[req_id] = payload
                    self._pending[req_id].set()

    def _merge_status(self, payload: dict) -> None:
        """将状态 payload 合并到 _status_cache。

        支持两种格式：
          A) 扁平状态 dict: {"name":"lrkcapture","status":"CONNECTED",...}
             → 存为 _status_cache["lrkcapture"]
          B) 键值对包裹: {"lrkcapture:host:port": {"name":"lrkcapture",...}}
             → 按 val["name"] 存储
        """
        if not isinstance(payload, dict):
            return
        # 情况 A：payload 自身就是 proto.get_status() 的扁平返回
        if "name" in payload and "status" in payload:
            name = payload["name"]
            self._status_cache[name] = dict(payload)
            return
        # 情况 B：外层 key 包裹的批量状态
        for key, val in payload.items():
            if isinstance(val, dict) and "name" in val:
                self._status_cache[val["name"]] = val
            elif isinstance(val, dict) and "status" in val:
                self._status_cache[key] = val
            else:
                self._status_cache[key] = val

    # ── 命令发送 ──────────────────────────────────────────────

    def send_command(self, cmd_type: str, **kwargs: Any) -> dict:
        """向子进程发送命令并等待响应。"""
        if self._process is None or not self._process.is_alive():
            return {"error": "协议管理子进程未运行"}

        req_id = uuid.uuid4().hex[:12]
        event = threading.Event()

        with self._lock:
            self._pending[req_id] = event

        cmd = {"type": cmd_type, "request_id": req_id, **kwargs}
        self._cmd_q.put(cmd)

        # 等待响应（最多 15 秒）
        if event.wait(timeout=15.0):
            with self._lock:
                resp = self._responses.pop(req_id, {})
                self._pending.pop(req_id, None)
            return resp
        else:
            with self._lock:
                self._pending.pop(req_id, None)
            return {"error": "命令超时"}

    # ── 状态查询 ──────────────────────────────────────────────

    def get_status(self) -> dict:
        """获取缓存的连接状态。"""
        with self._lock:
            return dict(self._status_cache)

    def get_messages(self, since: float = 0.0) -> list[dict]:
        """获取 since 时间戳之后的新报文。"""
        with self._lock:
            return [m for m in self._message_buffer if m.get("timestamp", 0) > since]

    def clear_messages(self, host: str, port: int, protocol_type: str) -> dict:
        """清空主进程报文缓冲区，并通知子进程清空协议实例报文。"""
        with self._lock:
            self._message_buffer.clear()
        # 通知子进程同步清空
        return self.send_command(
            CMD_CLEAR_MESSAGES,
            host=host,
            port=port,
            protocol_type=protocol_type,
        )


# 全局单例
protocol_manager = ProtocolManager()
