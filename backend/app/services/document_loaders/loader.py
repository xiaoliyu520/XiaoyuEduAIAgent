import logging
from typing import Optional, List

from app.services.document_loaders.image_loader import ImageLoader
from app.services.document_loaders.pdf_loader import PDFLoader
from app.services.document_loaders.doc_loader import DocLoader
from app.services.document_loaders.ppt_loader import PPTLoader
from app.services.document_loaders.csv_loader import CSVLoader

logger = logging.getLogger(__name__)


class DocumentLoader:
    @classmethod
    def get_extension(cls, filename: str) -> str:
        return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    @classmethod
    def load_from_bytes(
        cls,
        file_data: bytes,
        filename: str,
        csv_columns: Optional[List[str]] = None,
    ) -> str:
        ext = cls.get_extension(filename)
        logger.info(f"Loading document: {filename}, extension: {ext}, size: {len(file_data)} bytes")

        try:
            if ImageLoader.is_supported(filename):
                logger.info(f"Using ImageLoader for {filename}")
                result = ImageLoader.load_from_bytes(file_data)
                logger.info(f"ImageLoader extracted {len(result)} characters")
                return result

            if PDFLoader.is_supported(filename):
                logger.info(f"Using PDFLoader for {filename}")
                result = PDFLoader.load_from_bytes(file_data)
                logger.info(f"PDFLoader extracted {len(result)} characters")
                return result

            if DocLoader.is_supported(filename):
                logger.info(f"Using DocLoader for {filename}")
                result = DocLoader.load_from_bytes(file_data)
                logger.info(f"DocLoader extracted {len(result)} characters")
                return result

            if PPTLoader.is_supported(filename):
                logger.info(f"Using PPTLoader for {filename}")
                result = PPTLoader.load_from_bytes(file_data)
                logger.info(f"PPTLoader extracted {len(result)} characters")
                return result

            if CSVLoader.is_supported(filename):
                logger.info(f"Using CSVLoader for {filename}")
                result = CSVLoader.load_from_bytes(file_data, columns_to_read=csv_columns)
                logger.info(f"CSVLoader extracted {len(result)} characters")
                return result

            if ext in {".txt", ".md"}:
                logger.info(f"Using text decoder for {filename}")
                result = file_data.decode("utf-8", errors="ignore")
                logger.info(f"Text decoder extracted {len(result)} characters")
                return result

            logger.warning(f"Unknown file type: {ext}, trying UTF-8 decode")
            return file_data.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Failed to load document {filename}: {e}", exc_info=True)
            raise

    @classmethod
    def load_from_file(cls, file_path: str, csv_columns: Optional[List[str]] = None) -> str:
        import os

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f.read(), filename, csv_columns)

    @classmethod
    def get_supported_extensions(cls) -> set:
        return (
            ImageLoader.SUPPORTED_EXTENSIONS
            | PDFLoader.SUPPORTED_EXTENSIONS
            | DocLoader.SUPPORTED_EXTENSIONS
            | PPTLoader.SUPPORTED_EXTENSIONS
            | CSVLoader.SUPPORTED_EXTENSIONS
            | {".txt", ".md"}
        )
