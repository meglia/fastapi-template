"""YOLO 目标检测相关数据模型。"""

from pydantic import BaseModel, Field


class DetectionBox(BaseModel):
    """单个检测框。"""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str


class YoloResponse(BaseModel):
    """YOLO 检测响应。"""

    filename: str
    detections: list[DetectionBox] = []
    count: int = 0
    inference_time_ms: float = 0.0

    def model_post_init(self, __context) -> None:
        self.count = len(self.detections)
