import logging
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image

from app.services.document_loaders.ocr import get_ocr

logger = logging.getLogger(__name__)


class ImageLoader:
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    @classmethod
    def load_from_bytes(cls, file_data: bytes) -> str:
        try:
            image = Image.open(BytesIO(file_data))
            logger.info(f"Image opened: mode={image.mode}, size={image.size}")

            if image.mode != "RGB":
                image = image.convert("RGB")
                logger.info(f"Converted image to RGB mode")

            img_array = np.array(image)
            logger.info(f"Image array shape: {img_array.shape}")

            ocr = get_ocr()
            result, _ = ocr(img_array)
            logger.info(f"OCR result: {len(result) if result else 0} text blocks")

            if result:
                ocr_result = [line[1] for line in result]
                text = "\n".join(ocr_result)
                logger.info(f"Extracted text length: {len(text)}")
                return text

            logger.warning("OCR returned no results")
            return ""

        except Exception as e:
            logger.error(f"ImageLoader error: {e}", exc_info=True)
            raise

    @classmethod
    def load_from_file(cls, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f.read())

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_EXTENSIONS
