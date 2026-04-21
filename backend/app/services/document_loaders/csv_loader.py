import csv
from io import BytesIO, TextIOWrapper
from typing import Optional, List

from app.services.document_loaders.helpers import detect_file_encodings


class CSVLoader:
    SUPPORTED_EXTENSIONS = {".csv"}

    @classmethod
    def load_from_bytes(
        cls,
        file_data: bytes,
        columns_to_read: Optional[List[str]] = None,
        encoding: Optional[str] = None,
        autodetect_encoding: bool = True,
    ) -> str:
        columns_to_read = columns_to_read or []

        if encoding:
            try:
                return cls._read_csv(file_data, encoding, columns_to_read)
            except UnicodeDecodeError:
                pass

        if autodetect_encoding:
            detected = detect_file_encodings(file_data)
            for enc in detected:
                try:
                    return cls._read_csv(file_data, enc.encoding, columns_to_read)
                except UnicodeDecodeError:
                    continue

        try:
            return cls._read_csv(file_data, "utf-8", columns_to_read)
        except UnicodeDecodeError:
            return cls._read_csv(file_data, "gbk", columns_to_read)

    @classmethod
    def _read_csv(cls, file_data: bytes, encoding: str, columns_to_read: List[str]) -> str:
        text_io = TextIOWrapper(BytesIO(file_data), encoding=encoding)
        reader = csv.DictReader(text_io)

        content_parts = []
        for i, row in enumerate(reader):
            if columns_to_read:
                row_content = []
                for col in columns_to_read:
                    if col in row:
                        row_content.append(f"{col}: {row[col]}")
                if row_content:
                    content_parts.append("\n".join(row_content))
            else:
                row_content = [f"{k}: {v}" for k, v in row.items()]
                content_parts.append("\n".join(row_content))

        return "\n\n".join(content_parts)

    @classmethod
    def load_from_file(
        cls,
        file_path: str,
        columns_to_read: Optional[List[str]] = None,
        encoding: Optional[str] = None,
        autodetect_encoding: bool = True,
    ) -> str:
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f.read(), columns_to_read, encoding, autodetect_encoding)

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_EXTENSIONS
