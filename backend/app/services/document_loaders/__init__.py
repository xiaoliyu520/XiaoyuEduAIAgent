from app.services.document_loaders.loader import DocumentLoader
from app.services.document_loaders.image_loader import ImageLoader
from app.services.document_loaders.pdf_loader import PDFLoader
from app.services.document_loaders.doc_loader import DocLoader
from app.services.document_loaders.ppt_loader import PPTLoader
from app.services.document_loaders.csv_loader import CSVLoader
from app.services.document_loaders.ocr import get_ocr

__all__ = [
    "DocumentLoader",
    "ImageLoader",
    "PDFLoader",
    "DocLoader",
    "PPTLoader",
    "CSVLoader",
    "get_ocr",
]
