import os
import logging
import numpy as np
from typing import Optional
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_reranker: Optional[any] = None
_reranker_available: Optional[bool] = None


def _normalize_scores(scores):
    if isinstance(scores, (float, int, np.floating, np.integer)):
        return [float(scores)]
    if isinstance(scores, np.ndarray):
        return scores.tolist()
    if isinstance(scores, list):
        return [float(s) for s in scores]
    return [float(scores)]


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _format_scores(score_list, key=None):
    if key:
        return [f"{d[key]:.3f}" for d in score_list]
    return [f"{s:.3f}" for s in score_list]


def get_reranker():
    global _reranker, _reranker_available
    
    if not settings.ENABLE_RERANKER:
        logger.debug("重排序模型未启用 (ENABLE_RERANKER=false)")
        _reranker_available = False
        return None
    
    if _reranker_available is False:
        logger.debug("重排序模型不可用，跳过加载")
        return None
    
    if _reranker is None:
        try:
            logger.info(f"开始加载重排序模型: {settings.RERANKER_MODEL_NAME}")
            if settings.HF_MIRROR_URL:
                os.environ["HF_ENDPOINT"] = settings.HF_MIRROR_URL
                logger.info(f"使用HuggingFace镜像: {settings.HF_MIRROR_URL}")
            
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(
                settings.RERANKER_MODEL_NAME,
                max_length=512,
            )
            _reranker_available = True
            logger.info("重排序模型加载成功")
        except Exception as e:
            logger.warning(f"重排序模型加载失败，将使用降级方案: {e}")
            _reranker_available = False
            return None
    
    return _reranker


def rerank(query: str, documents: list[str], top_k: int = 3) -> list[dict]:
    reranker = get_reranker()
    if not documents:
        logger.debug("无文档需要重排序")
        return []
    
    logger.debug(f"开始重排序: query='{query[:30]}...', docs={len(documents)}, top_k={top_k}")
    
    if reranker is None:
        logger.info("使用BM25降级方案进行重排序")
        return _fallback_rerank(query, documents, top_k)
    
    pairs = [[query, doc] for doc in documents]
    scores = reranker.predict(pairs)
    scores = _normalize_scores(scores)
    scores = [_sigmoid(s) for s in scores]
    
    scored_docs = list(zip(documents, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    results = []
    for doc, score in scored_docs[:top_k]:
        results.append({
            "content": doc,
            "score": float(score),
        })
    
    score_strs = _format_scores([r["score"] for r in results])
    logger.info(f"重排序完成(CrossEncoder): top_k={len(results)}, scores={score_strs}")
    return results


def rerank_with_metadata(
    query: str,
    documents: list[dict],
    content_key: str = "content",
    top_k: int = 3,
) -> list[dict]:
    if not documents:
        logger.debug("无文档需要重排序")
        return []
    
    logger.debug(f"开始重排序(带元数据): query='{query[:30]}...', docs={len(documents)}, top_k={top_k}")
    
    reranker = get_reranker()
    
    if reranker is None:
        logger.info("使用BM25降级方案进行重排序")
        return _fallback_rerank_with_metadata(query, documents, content_key, top_k)
    
    contents = [doc[content_key] for doc in documents]
    pairs = [[query, content] for content in contents]
    scores = reranker.predict(pairs)
    scores = _normalize_scores(scores)
    scores = [_sigmoid(s) for s in scores]
    
    for i, score in enumerate(scores):
        documents[i]["rerank_score"] = float(score)
    documents.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    result = documents[:top_k]
    score_strs = _format_scores(result, key="rerank_score")
    logger.info(f"重排序完成(CrossEncoder): top_k={len(result)}, scores={score_strs}")
    return result


def _fallback_rerank(query: str, documents: list[str], top_k: int = 3) -> list[dict]:
    from rank_bm25 import BM25Okapi
    import jieba
    
    tokenized_corpus = [list(jieba.cut(doc)) for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = list(jieba.cut(query))
    scores = bm25.get_scores(tokenized_query)
    
    scored_docs = list(zip(documents, scores))
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    results = []
    max_score = float(max(scores)) if len(scores) > 0 and max(scores) > 0 else 1.0
    for doc, score in scored_docs[:top_k]:
        normalized_score = min(float(score) / max_score, 1.0) if max_score > 0 and score > 0 else 0.0
        results.append({
            "content": doc,
            "score": normalized_score,
        })
    
    score_strs = _format_scores([r["score"] for r in results])
    logger.info(f"重排序完成(BM25降级): top_k={len(results)}, scores={score_strs}")
    return results


def _fallback_rerank_with_metadata(
    query: str,
    documents: list[dict],
    content_key: str = "content",
    top_k: int = 3,
) -> list[dict]:
    from rank_bm25 import BM25Okapi
    import jieba
    
    contents = [doc[content_key] for doc in documents]
    tokenized_corpus = [list(jieba.cut(content)) for content in contents]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = list(jieba.cut(query))
    scores = bm25.get_scores(tokenized_query)
    
    max_score = float(max(scores)) if len(scores) > 0 and max(scores) > 0 else 1.0
    for i, score in enumerate(scores):
        documents[i]["rerank_score"] = min(float(score) / max_score, 1.0) if max_score > 0 and score > 0 else 0.0
    
    documents.sort(key=lambda x: x["rerank_score"], reverse=True)
    result = documents[:top_k]
    
    score_strs = _format_scores(result, key="rerank_score")
    logger.info(f"重排序完成(BM25降级): top_k={len(result)}, scores={score_strs}")
    return result
