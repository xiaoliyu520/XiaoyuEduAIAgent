import os
from typing import Optional
from langchain_community.embeddings import DashScopeEmbeddings
from app.core.config import get_settings

settings = get_settings()

_embedding_model: Optional[DashScopeEmbeddings] = None


def get_embedding_model() -> DashScopeEmbeddings:
    global _embedding_model
    if _embedding_model is None:
        os.environ["DASHSCOPE_API_KEY"] = settings.DASHSCOPE_API_KEY
        _embedding_model = DashScopeEmbeddings(
            model=settings.EMBEDDING_MODEL_NAME,
        )
    return _embedding_model


async def embed_query(text: str) -> list[float]:
    model = get_embedding_model()
    result = await model.aembed_query(text)
    return result


async def embed_documents(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    result = await model.aembed_documents(texts)
    return result
