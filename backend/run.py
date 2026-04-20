import os

from app.core.config import get_settings
settings = get_settings()

os.environ["HF_ENDPOINT"] = settings.HF_MIRROR_URL
os.environ["HUGGINGFACE_HUB_URL"] = settings.HF_MIRROR_URL

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
