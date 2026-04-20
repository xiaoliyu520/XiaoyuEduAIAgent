import jieba
from rank_bm25 import BM25Okapi
from typing import Optional
import json
import pickle
import asyncio
import logging

from app.core.redis import get_redis, get_redis_bytes
from app.mcp.milvus.client import load_all_documents_from_milvus

logger = logging.getLogger(__name__)


BM25_TTL = 86400 * 7


def _normalize_metadata(metadata) -> dict:
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    if "doc_status" not in metadata:
        metadata["doc_status"] = "active"
    return metadata


class BM25Index:
    def __init__(self):
        self._indices: dict[str, "BM25IndexInstance"] = {}
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            self._redis = await get_redis_bytes()
        return self._redis

    async def build_index(self, collection_name: str, documents: list[dict]):
        for doc in documents:
            doc["metadata"] = _normalize_metadata(doc.get("metadata", {}))
        tokenized_corpus = []
        for doc in documents:
            tokens = list(jieba.cut(doc["content"]))
            tokenized_corpus.append(tokens)
        bm25 = BM25Okapi(tokenized_corpus)
        self._indices[collection_name] = BM25IndexInstance(
            bm25=bm25,
            documents=documents,
        )
        await self._save_to_redis(collection_name, documents)

    async def add_documents(self, collection_name: str, new_documents: list[dict]):
        for doc in new_documents:
            doc["metadata"] = _normalize_metadata(doc.get("metadata", {}))
        
        await self.ensure_index(collection_name)
        
        if collection_name not in self._indices:
            logger.info(f"BM25索引不存在，创建新索引: {collection_name}")
            await self.build_index(collection_name, new_documents)
            return
        
        index = self._indices[collection_name]
        
        existing_chunk_ids = set()
        for doc in index.documents:
            chunk_id = doc.get("chunk_id", "")
            if chunk_id:
                existing_chunk_ids.add(chunk_id)
        
        docs_to_add = []
        for doc in new_documents:
            chunk_id = doc.get("chunk_id", "")
            if chunk_id and chunk_id not in existing_chunk_ids:
                docs_to_add.append(doc)
        
        if not docs_to_add:
            logger.info(f"BM25索引无需更新，所有文档已存在: {collection_name}")
            return
        
        logger.info(f"BM25索引添加文档: {collection_name}, 新增文档数: {len(docs_to_add)}")
        index.documents.extend(docs_to_add)
        
        tokenized_corpus = []
        for doc in index.documents:
            tokens = list(jieba.cut(doc["content"]))
            tokenized_corpus.append(tokens)
        index.bm25 = BM25Okapi(tokenized_corpus)
        
        await self._save_to_redis(collection_name, index.documents)

    async def _save_to_redis(self, collection_name: str, documents: list[dict]):
        try:
            redis = await self._get_redis()
            key = f"bm25:{collection_name}"
            data = pickle.dumps(documents)
            await redis.set(key, data, ex=BM25_TTL)
            logger.info(f"BM25索引保存到Redis成功: {collection_name}, 文档数: {len(documents)}")
        except Exception as e:
            logger.error(f"BM25索引保存到Redis失败: {collection_name}, 错误: {e}")

    async def _load_from_redis(self, collection_name: str) -> bool:
        if collection_name in self._indices:
            return True
        try:
            redis = await self._get_redis()
            key = f"bm25:{collection_name}"
            data = await redis.get(key)
            if data:
                documents = pickle.loads(data)
                for doc in documents:
                    doc["metadata"] = _normalize_metadata(doc.get("metadata", {}))
                tokenized_corpus = []
                for doc in documents:
                    tokens = list(jieba.cut(doc["content"]))
                    tokenized_corpus.append(tokens)
                bm25 = BM25Okapi(tokenized_corpus)
                self._indices[collection_name] = BM25IndexInstance(
                    bm25=bm25,
                    documents=documents,
                )
                logger.info(f"BM25索引从Redis加载成功: {collection_name}, 文档数: {len(documents)}")
                return True
        except Exception as e:
            logger.warning(f"BM25索引从Redis加载失败: {collection_name}, 错误: {e}")
        return False

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 20,
        exclude_archived: bool = True,
    ) -> list[dict]:
        if collection_name not in self._indices:
            return []
        index = self._indices[collection_name]
        tokenized_query = list(jieba.cut(query))
        scores = index.bm25.get_scores(tokenized_query)
        scored_docs = list(zip(index.documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        results = []
        for doc, score in scored_docs:
            if score <= 0:
                break
            if exclude_archived and doc.get("metadata", {}).get("doc_status") == "archived":
                continue
            results.append({
                **doc,
                "score": float(score),
            })
            if len(results) >= top_k:
                break
        return results

    def has_index(self, collection_name: str) -> bool:
        return collection_name in self._indices

    async def ensure_index(self, collection_name: str) -> bool:
        if collection_name in self._indices:
            return True
        
        if await self._load_from_redis(collection_name):
            return True
        
        documents = load_all_documents_from_milvus(collection_name)
        if documents:
            for doc in documents:
                doc["metadata"] = _normalize_metadata(doc.get("metadata", {}))
            tokenized_corpus = []
            for doc in documents:
                tokens = list(jieba.cut(doc["content"]))
                tokenized_corpus.append(tokens)
            bm25 = BM25Okapi(tokenized_corpus)
            self._indices[collection_name] = BM25IndexInstance(
                bm25=bm25,
                documents=documents,
            )
            await self._save_to_redis(collection_name, documents)
            return True
        
        return False

    def remove_index(self, collection_name: str):
        if collection_name in self._indices:
            del self._indices[collection_name]
        asyncio.create_task(self._remove_from_redis(collection_name))

    async def _remove_from_redis(self, collection_name: str):
        try:
            redis = await self._get_redis()
            key = f"bm25:{collection_name}"
            await redis.delete(key)
            logger.info(f"BM25索引从Redis删除成功: {collection_name}")
        except Exception as e:
            logger.error(f"BM25索引从Redis删除失败: {collection_name}, 错误: {e}")

    async def update_document_status(self, collection_name: str, doc_title: str, new_status: str):
        await self.ensure_index(collection_name)
        if collection_name not in self._indices:
            return
        index = self._indices[collection_name]
        updated = False
        for doc in index.documents:
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "")
            if source == doc_title or source == doc_title.split("/")[-1]:
                metadata["doc_status"] = new_status
                doc["metadata"] = metadata
                updated = True
        if updated:
            await self._save_to_redis(collection_name, index.documents)

    async def remove_document(self, collection_name: str, doc_title: str):
        await self.ensure_index(collection_name)
        if collection_name not in self._indices:
            logger.info(f"BM25索引不存在，无需删除: {collection_name}")
            return
        index = self._indices[collection_name]
        original_count = len(index.documents)
        index.documents = [
            doc for doc in index.documents
            if doc.get("metadata", {}).get("source") != doc_title
            and doc.get("metadata", {}).get("source") != doc_title.split("/")[-1]
        ]
        removed_count = original_count - len(index.documents)
        if removed_count > 0:
            logger.info(f"BM25索引删除文档: {collection_name}, 删除文档数: {removed_count}")
            if len(index.documents) == 0:
                del self._indices[collection_name]
                await self._remove_from_redis(collection_name)
            else:
                tokenized_corpus = []
                for doc in index.documents:
                    tokens = list(jieba.cut(doc["content"]))
                    tokenized_corpus.append(tokens)
                index.bm25 = BM25Okapi(tokenized_corpus)
                await self._save_to_redis(collection_name, index.documents)
        else:
            logger.info(f"BM25索引未找到要删除的文档: {collection_name}, doc_title: {doc_title}")


class BM25IndexInstance:
    def __init__(self, bm25: BM25Okapi, documents: list[dict]):
        self.bm25 = bm25
        self.documents = documents


bm25_index = BM25Index()


def get_bm25_index() -> BM25Index:
    return bm25_index
