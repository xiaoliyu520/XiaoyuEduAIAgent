from typing import Optional
from FlagEmbedding import FlagReranker
from app.core.config import get_settings

settings = get_settings()

_reranker: Optional[FlagReranker] = None


def get_reranker() -> FlagReranker:
    global _reranker
    if _reranker is None:
        _reranker = FlagReranker(
            settings.RERANKER_MODEL_NAME,
            use_fp16=True,
        )
    return _reranker


def rerank(query: str, documents: list[str], top_k: int = 3) -> list[dict]:
    reranker = get_reranker()
    if not documents:
        return []
    pairs = [[query, doc] for doc in documents]
    scores = reranker.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    scored_docs = list(zip(documents, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    results = []
    for doc, score in scored_docs[:top_k]:
        results.append({
            "content": doc,
            "score": float(score),
        })
    return results


def rerank_with_metadata(
    query: str,
    documents: list[dict],
    content_key: str = "content",
    top_k: int = 3,
) -> list[dict]:
    if not documents:
        return []
    contents = [doc[content_key] for doc in documents]
    reranker = get_reranker()
    pairs = [[query, content] for content in contents]
    scores = reranker.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    for i, score in enumerate(scores):
        documents[i]["rerank_score"] = float(score)
    documents.sort(key=lambda x: x["rerank_score"], reverse=True)
    return documents[:top_k]
