from minio import Minio
from app.core.config import get_settings

settings = get_settings()

_minio_client: Minio | None = None


def get_minio() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        _ensure_bucket(_minio_client, settings.MINIO_BUCKET)
    return _minio_client


def _ensure_bucket(client: Minio, bucket: str):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


async def upload_file(object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
    import io
    client = get_minio()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        data=io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type,
    )
    return object_name


async def download_file(object_name: str) -> bytes:
    client = get_minio()
    response = client.get_object(bucket_name=settings.MINIO_BUCKET, object_name=object_name)
    data = response.read()
    response.close()
    response.release_conn()
    return data


async def delete_file(object_name: str):
    client = get_minio()
    client.remove_object(bucket_name=settings.MINIO_BUCKET, object_name=object_name)
