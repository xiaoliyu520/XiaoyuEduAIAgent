from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image
from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from app.services.document_loaders.ocr import get_ocr


class DocLoader:
    SUPPORTED_EXTENSIONS = {".doc", ".docx"}

    @classmethod
    def _iter_block_items(cls, parent):
        if isinstance(parent, _Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        else:
            return

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    @classmethod
    def load_from_bytes(cls, file_data: bytes) -> str:
        doc = Document(BytesIO(file_data))
        resp = ""

        ocr = get_ocr()

        for block in cls._iter_block_items(doc):
            if isinstance(block, Paragraph):
                resp += block.text.strip() + "\n"

                images = block._element.xpath(".//pic:pic")
                for image in images:
                    for img_id in image.xpath(".//a:blip/@r:embed"):
                        part = doc.part.related_parts.get(img_id)
                        if part is None:
                            continue
                        try:
                            from docx.image.image import Image as DocxImage

                            if hasattr(part, "blob"):
                                pil_image = Image.open(BytesIO(part.blob))
                                if pil_image.mode != "RGB":
                                    pil_image = pil_image.convert("RGB")
                                img_array = np.array(pil_image)

                                result, _ = ocr(img_array)
                                if result:
                                    ocr_result = [line[1] for line in result]
                                    resp += "\n".join(ocr_result)
                        except Exception:
                            continue

            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            resp += paragraph.text.strip() + "\n"

        return resp

    @classmethod
    def load_from_file(cls, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f.read())

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_EXTENSIONS
