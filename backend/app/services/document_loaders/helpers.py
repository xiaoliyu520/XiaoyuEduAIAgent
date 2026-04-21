from typing import List, NamedTuple
import codecs


class FileEncoding(NamedTuple):
    encoding: str
    confidence: float


def detect_file_encodings(file_data: bytes) -> List[FileEncoding]:
    encodings = []

    try:
        import chardet
        result = chardet.detect(file_data[:10000])
        if result["encoding"]:
            encodings.append(FileEncoding(result["encoding"], result["confidence"]))
    except ImportError:
        pass

    common_encodings = ["utf-8", "gbk", "gb2312", "utf-16", "utf-16-le", "utf-16-be", "latin-1"]
    for enc in common_encodings:
        if not any(e.encoding.lower() == enc.lower() for e in encodings):
            encodings.append(FileEncoding(enc, 0.5))

    return encodings
