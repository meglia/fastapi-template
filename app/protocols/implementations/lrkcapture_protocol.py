"""LRK-CAPTURE 私有协议实现 — 基于 BaseProtocol 的 TCP 客户端。

适配自 lrkcapture_client.py，支持：
  - TCP 连接 / 断开
  - STARTDT act 启动数据传输
  - I/U/S 帧构建与解析
  - 0xFB 信号体解析
  - 收发报文统一记录到 _log_message()
  - 接收循环运行在独立 daemon 线程中
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from typing import Any

from app.protocols.base import BaseProtocol, ConnectionStatus, ProtocolConfig

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════════

U_STARTDT_ACT = 0x04

TYPE_NAMES: dict[int, str] = {
    0xAA: "普通报文",
    0xFB: "遥控报文",
    0xEE: "连接状态",
}

U_FRAME_NAMES: dict[int, str] = {
    0x04: "STARTDT act",
    0x08: "STARTDT con",
    0x10: "STOPDT act",
    0x20: "STOPDT con",
    0x40: "TESTFR act",
    0x80: "TESTFR con",
}


# ═══════════════════════════════════════════════════════════════════
#  LRK-CAPTURE 协议实现
# ═══════════════════════════════════════════════════════════════════

class LRKCAPYUREProtocol(BaseProtocol):
    """LRK-CAPTURE TCP 客户端协议实现。"""

    name = "lrkcapture"

    def __init__(self) -> None:
        super().__init__()
        self._sock: socket.socket | None = None
        self._recv_thread: threading.Thread | None = None
        self._running = False

        # 序列号
        self._send_seq = 0
        self._recv_seq = 0

        # 统计
        self._i_sent = 0
        self._i_recv = 0

        # 只接收遥控报文标志（True 时非 0xFB 帧不记日志）
        self._remote_only = False

    # ── 连接 / 断开 ──────────────────────────────────────────

    def connect(self) -> None:
        """建立 TCP 连接并发送 STARTDT act，然后启动接收线程。"""
        cfg = self._config

        self._status = ConnectionStatus.CONNECTING
        self._status_message = f"正在连接 {cfg.host}:{cfg.port}..."

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((cfg.host, cfg.port))
            self._sock.settimeout(None)

            # 发送 STARTDT act
            self._send_startdt_act()

            self._running = True
            self._status = ConnectionStatus.CONNECTED
            self._status_message = f"已连接 {cfg.host}:{cfg.port}"
            logger.info("LRKCAPYURE: %s", self._status_message)

            # 启动接收线程
            self._recv_thread = threading.Thread(
                target=self._recv_loop, daemon=True, name="lrkcapture-recv"
            )
            self._recv_thread.start()

        except Exception as e:
            self._status = ConnectionStatus.ERROR
            self._status_message = str(e)
            self._sock = None
            raise

    def disconnect(self) -> None:
        """断开连接并停止接收线程。"""
        self._running = False

        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        if self._recv_thread is not None:
            self._recv_thread.join(timeout=3.0)
            self._recv_thread = None

        self._status = ConnectionStatus.DISCONNECTED
        self._status_message = "已断开"
        logger.info("LRKCAPYURE: 已断开连接")

    def set_remote_only(self, enabled: bool) -> None:
        """设置只接收遥控报文模式。True 时非 0xFB 帧不记日志，缓冲区不被普通报文挤占。"""
        self._remote_only = enabled
        logger.info("LRKCAPYURE: 遥控报文过滤 = %s", "ON" if enabled else "OFF")

    def get_status(self) -> dict:
        s = super().get_status()
        s["remote_only"] = self._remote_only
        return s

    def send(self, data: bytes) -> None:
        """发送原始 I 帧（data 作为 ASDU 信息体）。"""
        if not self._sock or not self.is_connected():
            raise ConnectionError("未连接")
        asdu = self._build_asdu(0xAA, data)
        frame = self._build_frame(self._build_control_i(), asdu)
        desc = f"I N(S)={self._send_seq} N(R)={self._recv_seq}"
        self._send_raw(frame, frame_type="I", asdu_type=0xAA, desc=desc)
        self._i_sent += 1

    # ── 帧构建 ───────────────────────────────────────────────

    @staticmethod
    def _build_control_u(u_type: int) -> bytes:
        return struct.pack("<I", u_type | 0x03)

    def _build_control_i(self) -> bytes:
        self._send_seq = (self._send_seq + 1) & 0x7FFF
        return struct.pack("<HH", self._send_seq << 1, self._recv_seq << 1)

    @staticmethod
    def _build_control_s(nr: int) -> bytes:
        return struct.pack("<HH", 0x01, nr << 1)

    def _build_frame(self, control: bytes, asdu: bytes = b"") -> bytes:
        length = 4 + len(asdu)
        return struct.pack("<B", 0x68) + struct.pack("<I", length) + control + asdu

    def _build_asdu(
        self,
        atype: int,
        info: bytes = b"",
        vsq: int = 1,
        cot: int = 7,
        fun: int = 0,
        inf: int = 0,
        rii: int = 0,
    ) -> bytes:
        asdu_addr = self._config.extra.get("asdu_addr", 0x0001)
        return (
            struct.pack("<BBBHB", atype, vsq, cot, asdu_addr, fun)
            + struct.pack("<BB", inf, rii)
            + info
        )

    # ── 帧解析 ───────────────────────────────────────────────

    def _parse_control(self, ctrl: bytes) -> dict:
        b0 = ctrl[0]
        low = b0 & 0x03
        if low == 3:  # U
            utype = b0 & 0xFC
            return {
                "fmt": "U",
                "u_type": utype,
                "u_name": U_FRAME_NAMES.get(utype, f"U(0x{utype:02X})"),
            }
        if low == 1:  # S
            nr = struct.unpack_from("<H", ctrl, 2)[0] >> 1
            return {"fmt": "S", "nr": nr}
        # I
        ns = struct.unpack_from("<H", ctrl, 0)[0] >> 1
        nr = struct.unpack_from("<H", ctrl, 2)[0] >> 1
        return {"fmt": "I", "ns": ns, "nr": nr}

    def _parse_frame(self, data: bytes) -> dict | None:
        if len(data) < 9 or data[0] != 0x68:
            return None
        length = struct.unpack_from("<I", data, 1)[0]
        frame_total = 1 + 4 + length
        if len(data) < frame_total:
            return None

        result = self._parse_control(data[5:9])
        if result["fmt"] in ("U", "S"):
            return result

        asdu_off = 9
        asdu_len = frame_total - asdu_off
        if asdu_len >= 8:
            buf = data[asdu_off:frame_total]
            result["asdu"] = {
                "type": buf[0],
                "vsq": buf[1],
                "cot": buf[2],
                "addr": struct.unpack_from("<H", buf, 3)[0],
                "fun": buf[5],
                "inf": buf[6],
                "rii": buf[7],
                "info": buf[8:] if len(buf) > 8 else b"",
            }
        return result

    # ── 0xFB 信号解析 ────────────────────────────────────────

    @staticmethod
    def _parse_signal(info: bytes) -> dict | None:
        if len(info) < 410:
            return None

        def _cstr(data: bytes, offset: int, maxlen: int, enc: str = "utf-8") -> str:
            chunk = data[offset : offset + maxlen]
            end = chunk.find(b"\x00")
            return (chunk[:end] if end >= 0 else chunk).decode(enc, errors="replace")

        sig = {
            "path": _cstr(info, 12, 128, "ascii"),
            "description": _cstr(info, 140, 200, "utf-8"),
            "short_description": _cstr(info, 340, 64, "utf-8"),
            "timestamp": struct.unpack_from("<I", info, 404)[0],
            "state": info[408],
            "quality": info[409] if len(info) > 409 else None,
        }
        labels = {0x0A: "ON(合)", 0x0B: "OFF(分)"}
        sig["state_label"] = labels.get(sig["state"], f"未知(0x{sig['state']:02X})")
        return sig

    # ── 原始发送 / 记录 ──────────────────────────────────────

    def _send_raw(self, data: bytes, frame_type: str = "",
                  asdu_type: int | None = None, desc: str = "") -> None:
        if not self._sock:
            raise ConnectionError("未连接")
        self._sock.sendall(data)
        # 记录发送报文（可读描述，不显示原始字节）
        extra: dict[str, Any] = {}
        if frame_type:
            extra["frame_type"] = frame_type
        if asdu_type is not None:
            extra["asdu_type"] = asdu_type
        self._log_message("send", desc or "[发送]", **extra)

    def _send_startdt_act(self) -> None:
        frame = self._build_frame(self._build_control_u(U_STARTDT_ACT))
        self._send_raw(frame, frame_type="U", desc="U STARTDT act")
        logger.debug("  → 发送 STARTDT act")

    def _send_s(self) -> None:
        frame = self._build_frame(self._build_control_s(self._recv_seq))
        self._send_raw(frame, frame_type="S", desc=f"S N(R)={self._recv_seq}")
        logger.debug("  → 发送 S-frame N(R)=%d", self._recv_seq)

    # ── 接收循环 ─────────────────────────────────────────────

    def _recv_loop(self) -> None:
        buf = bytearray()
        while self._running:
            try:
                chunk = self._sock.recv(8192)
                if not chunk:
                    logger.warning("LRKCAPYURE: 连接被对端关闭")
                    self._running = False
                    self._status = ConnectionStatus.ERROR
                    self._status_message = "连接被对端关闭"
                    break
                buf.extend(chunk)

                # 逐帧消费
                while len(buf) >= 1:
                    if buf[0] != 0x68:
                        buf.pop(0)
                        continue
                    if len(buf) < 5:
                        break

                    length = struct.unpack_from("<I", bytes(buf), 1)[0]
                    frame_total = 1 + 4 + length
                    if len(buf) < frame_total:
                        break

                    frame_data = bytes(buf[:frame_total])
                    del buf[:frame_total]

                    parsed = self._parse_frame(frame_data)
                    if parsed:
                        self._handle_frame(parsed, frame_data)

            except socket.timeout:
                continue
            except OSError as e:
                if self._running:
                    logger.error("LRKCAPYURE 接收异常: %s", e)
                    self._status = ConnectionStatus.ERROR
                    self._status_message = str(e)
                break

        self._running = False
        # 清理残留 socket，确保重连时不会冲突
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ── 帧分发 ───────────────────────────────────────────────

    def _handle_frame(self, parsed: dict, frame_data: bytes = b"") -> None:
        fmt = parsed["fmt"]

        if fmt == "U":
            info = parsed.get("u_name", "unknown")
            logger.info("  ← U-frame: %s", info)
            self._log_message(
                "recv", f"U {info}",
                frame_type="U",
            )

        elif fmt == "S":
            nr = parsed["nr"]
            logger.debug("  ← S-frame N(R)=%d", nr)
            self._log_message(
                "recv", f"S N(R)={nr}",
                frame_type="S",
            )

        elif fmt == "I":
            ns = parsed["ns"]
            nr = parsed["nr"]
            asdu = parsed.get("asdu")
            if not asdu:
                return

            self._recv_seq = ns
            self._i_recv += 1

            atype = asdu["type"]

            # 遥控报文过滤模式：非 0xFB 帧只更新序列号，不记日志
            if self._remote_only and atype != 0xFB:
                logger.debug("  ← I-frame N(S)=%d type=0x%02X (filtered)", ns, atype)
                return

            detail = f"I N(S)={ns} N(R)={nr}"

            if atype == 0xFB:
                sig = self._parse_signal(asdu["info"])
                if sig:
                    ts_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(sig["timestamp"])
                    )
                    detail += (
                        f" | desc={sig['description']}"
                        f" | path={sig['path']}"
                        f" | state={sig['state_label']}(0x{sig['state']:02X})"
                        f" | ts={ts_str}"
                    )
                    self._log_message(
                        "recv", detail,
                        frame_type="I", asdu_type=atype,
                        signal={
                            "description": sig["description"],
                            "short_description": sig["short_description"],
                            "path": sig["path"],
                            "state": sig["state"],
                            "state_label": sig["state_label"],
                            "quality": sig["quality"],
                            "signal_ts": sig["timestamp"],
                            "signal_ts_str": ts_str,
                        },
                        hex=frame_data.hex(" "),
                    )
                else:
                    self._log_message(
                        "recv", detail + " | (信号解析失败)",
                        frame_type="I", asdu_type=atype,
                        hex=frame_data.hex(" "),
                    )
            elif atype == 0xEE:
                detail += f" | 连接状态信息体({len(asdu['info'])}B)"
                self._log_message(
                    "recv", detail,
                    frame_type="I", asdu_type=atype,
                )
            else:
                self._log_message(
                    "recv", detail,
                    frame_type="I", asdu_type=atype,
                )
            logger.info("  ← %s", detail)
