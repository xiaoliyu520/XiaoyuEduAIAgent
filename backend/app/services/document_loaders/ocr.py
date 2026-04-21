import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR

_ocr_instance: "RapidOCR" = None


def get_ocr() -> "RapidOCR":
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _ocr_instance = RapidOCR()
        except ImportError:
            raise ImportError("请安装 rapidocr_onnxruntime: pip install rapidocr_onnxruntime")
    return _ocr_instance
