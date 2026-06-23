"""视频服务 — OpenCV 设备枚举、线程安全连接管理与后台帧捕获。"""

import logging
import subprocess
import threading

import cv2

from app.models.video import VideoDevice, VideoStatus

logger = logging.getLogger(__name__)

# 尝试连接的最大设备索引数
MAX_DEVICE_INDEX = 10
# 分辨率候选（从高到低逐级回退）
RESOLUTION_CANDIDATES = [
    (1920, 1080),
    (1280, 720),
    (640, 480),
]


def _get_windows_camera_names() -> list[str]:
    """通过 PowerShell 获取 Windows 摄像头设备友好名称列表。"""
    try:
        cmd = (
            'powershell -NoProfile -Command '
            '"Get-PnpDevice -Class Camera -Status OK | '
            'Select-Object -ExpandProperty FriendlyName"'
        )
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
    except Exception:
        logger.debug("PowerShell 获取摄像头名称失败，使用回退命名", exc_info=True)
    return []


class VideoService:
    """视频设备管理服务（单例，线程安全）。

    同一时刻仅允许激活一个设备，后台线程持续抓帧，
    所有 HTTP 端点共享同一个 VideoService 实例，自然实现跨页面视频共享。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._cap: cv2.VideoCapture | None = None
        self._latest_frame: cv2.typing.MatLike | None = None
        self._active_device: VideoDevice | None = None
        self._resolution: dict[str, int] = {"width": 0, "height": 0}
        self._running = False
        self._thread: threading.Thread | None = None

    # ── 设备枚举 ──────────────────────────────────────

    def get_devices(self) -> list[VideoDevice]:
        """枚举当前系统所有可用的视频设备。

        已连接的设备直接复用缓存名称，避免重复打开干扰现有连接。
        """
        windows_names = _get_windows_camera_names()
        devices: list[VideoDevice] = []

        # 获取当前活跃设备信息（避免重复打开导致 DirectShow 驱动干扰）
        with self._lock:
            active_index = (
                self._active_device.device_index
                if self._active_device is not None
                else -1
            )
            active_name = (
                self._active_device.device_name
                if self._active_device is not None
                else None
            )

        for index in range(MAX_DEVICE_INDEX):
            # 当前已连接的设备：直接复用缓存名称，不再打开
            if index == active_index and active_name is not None:
                devices.append(
                    VideoDevice(device_index=index, device_name=active_name)
                )
                continue

            try:
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    name = self._pick_device_name(index, len(devices), windows_names)
                    devices.append(VideoDevice(device_index=index, device_name=name))
                    cap.release()
            except Exception:
                logger.debug("枚举设备 index=%d 失败", index, exc_info=True)

        logger.info("枚举到 %d 个视频设备", len(devices))
        return devices

    @staticmethod
    def _pick_device_name(
        index: int, ordinal: int, windows_names: list[str],
    ) -> str:
        """为给定索引用合适的名称（优先 Windows 真实设备名，其次序号命名）。"""
        if ordinal < len(windows_names):
            return windows_names[ordinal]
        return f"视频设备 {index}"

    # ── 连接管理 ──────────────────────────────────────

    def connect(self, device_index: int) -> None:
        """连接到指定设备，自动设置最高可用分辨率并启动后台抓帧。"""
        with self._lock:
            self._disconnect_internal()

            cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开视频设备 (index={device_index})")

            width, height = self._apply_best_resolution(cap)
            name = self._pick_device_name(
                device_index, device_index,
                _get_windows_camera_names(),
            )

            self._cap = cap
            self._active_device = VideoDevice(
                device_index=device_index, device_name=name,
            )
            self._resolution = {"width": width, "height": height}
            self._running = True

            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            logger.info(
                "已连接视频设备 index=%d name=%s resolution=%dx%d",
                device_index, name, width, height,
            )

    @staticmethod
    def _apply_best_resolution(cap: cv2.VideoCapture) -> tuple[int, int]:
        """按候选列表从高到低尝试设置分辨率，返回实际生效值。"""
        for w, h in RESOLUTION_CANDIDATES:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w > 0 and actual_h > 0:
                return actual_w, actual_h
        # 兜底：返回设备当前默认分辨率
        return (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def _capture_loop(self) -> None:
        """后台线程：持续从设备读取帧到缓存。"""
        while self._running:
            cap = self._cap
            if cap is None or not cap.isOpened():
                break
            ret, frame = cap.read()
            if ret:
                with self._frame_lock:
                    self._latest_frame = frame

    # ── 帧获取 ────────────────────────────────────────

    def get_raw_frame(self):
        """获取最新帧的原始 numpy 数组（BGR），无帧时返回 None。

        返回原始数组而非 JPEG 字节，便于调用方在编码前做图像处理（如打时标）。
        """
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_frame(self) -> bytes | None:
        """获取最新帧的 JPEG 编码字节，无帧时返回 None。"""
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            success, jpeg = cv2.imencode('.jpg', self._latest_frame)
            if not success:
                return None
            return jpeg.tobytes()

    # ── 断开连接 ──────────────────────────────────────

    def disconnect(self) -> None:
        """断开当前设备连接。"""
        with self._lock:
            self._disconnect_internal()

    def _disconnect_internal(self) -> None:
        """内部断开逻辑（调用方需持有 _lock）。"""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        self._active_device = None
        self._resolution = {"width": 0, "height": 0}
        self._latest_frame = None
        logger.info("已断开视频设备连接")

    # ── 状态查询 ──────────────────────────────────────

    def get_status(self) -> VideoStatus:
        """返回当前视频连接状态。"""
        with self._lock:
            connected = self._cap is not None and self._cap.isOpened()
            return VideoStatus(
                connected=connected,
                active_device=self._active_device,
                resolution=self._resolution,
            )


# ── 单例 ──────────────────────────────────────────────

_video_service: VideoService | None = None


def get_video_service() -> VideoService:
    """获取 VideoService 线程安全单例。"""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service
