from io import BytesIO
from typing import Optional

from PIL import Image
import numpy as np

from app.services.document_loaders.ocr import get_ocr


class PDFLoader:
    SUPPORTED_EXTENSIONS = {".pdf"}

    @classmethod
    def load_from_bytes(cls, file_data: bytes, ocr_threshold: tuple = (0.3, 0.3)) -> str:
        try:
            import fitz
        except ImportError:
            raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")

        doc = fitz.open(stream=file_data, filetype="pdf")
        resp = ""

        ocr = get_ocr()

        for page in doc:
            text = page.get_text("")
            resp += text + "\n"

            img_list = page.get_image_info(xrefs=True)
            for img in img_list:
                xref = img.get("xref")
                if not xref:
                    continue

                bbox = img["bbox"]
                if (bbox[2] - bbox[0]) / page.rect.width < ocr_threshold[0]:
                    continue
                if (bbox[3] - bbox[1]) / page.rect.height < ocr_threshold[1]:
                    continue

                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n < 4:
                        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                            pix.height, pix.width, -1
                        )
                    else:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                            pix.height, pix.width, -1
                        )

                    result, _ = ocr(img_array)
                    if result:
                        ocr_result = [line[1] for line in result]
                        resp += "\n".join(ocr_result)
                except Exception:
                    continue

        return resp

    @classmethod
    def load_from_file(cls, file_path: str, ocr_threshold: tuple = (0.3, 0.3)) -> str:
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f.read(), ocr_threshold)

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_EXTENSIONS
