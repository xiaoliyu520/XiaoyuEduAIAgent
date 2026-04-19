import jieba
from rank_bm25 import BM25Okapi
from typing import Optional
import json


class BM25Index:
    def __init__(self):
        self._indices: dict[str, "BM25IndexInstance"] = {}

    def build_index(self, collection_name: str, documents: list[dict]):
        tokenized_corpus = []
        for doc in documents:
            tokens = list(jieba.cut(doc["content"]))
            tokenized_corpus.append(tokens)
        bm25 = BM25Okapi(tokenized_corpus)
        self._indices[collection_name] = BM25IndexInstance(
            bm25=bm25,
            documents=documents,
        )

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 20,
    ) -> list[dict]:
        if collection_name not in self._indices:
            return []
        index = self._indices[collection_name]
        tokenized_query = list(jieba.cut(query))
        scores = index.bm25.get_scores(tokenized_query)
        scored_docs = list(zip(index.documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        results = []
        for doc, score in scored_docs[:top_k]:
            if score > 0:
                results.append({
                    **doc,
                    "score": float(score),
                })
        return results

    def has_index(self, collection_name: str) -> bool:
        return collection_name in self._indices

    def remove_index(self, collection_name: str):
        if collection_name in self._indices:
            del self._indices[collection_name]


class BM25IndexInstance:
    def __init__(self, bm25: BM25Okapi, documents: list[dict]):
        self.bm25 = bm25
        self.documents = documents


bm25_index = BM25Index()


def get_bm25_index() -> BM25Index:
    return bm25_index
