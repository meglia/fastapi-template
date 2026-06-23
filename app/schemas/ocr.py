"""PaddleOCR 文字识别相关数据模型。"""

from pydantic import BaseModel


class OCRBlock(BaseModel):
    """单个识别文本块。"""

    text: str
    confidence: float
    box: list[list[int]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]


class OCRResponse(BaseModel):
    """OCR 识别响应。"""

    filename: str
    blocks: list[OCRBlock] = []
    full_text: str = ""
    inference_time_ms: float = 0.0

    def model_post_init(self, __context) -> None:
        if not self.full_text:
            self.full_text = "\n".join(b.text for b in self.blocks)
