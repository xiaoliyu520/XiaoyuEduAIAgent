from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
from typing import Optional
from app.core.config import get_settings
from app.services.embedding.service import embed_query, embed_documents

settings = get_settings()

_milvus_client: Optional[MilvusClient] = None

DEFAULT_DIM = 1024


def get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient(
            uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
        )
    return _milvus_client


def ensure_collection(collection_name: str, dim: int = DEFAULT_DIM):
    client = get_milvus_client()
    if not client.has_collection(collection_name):
        schema = CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8000),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            ],
            description=f"Knowledge collection: {collection_name}",
        )
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
        )
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        client.create_index(
            collection_name=collection_name,
            index_params=index_params,
        )


async def insert_documents(
    collection_name: str,
    contents: list[str],
    metadatas: Optional[list[dict]] = None,
    chunk_ids: Optional[list[str]] = None,
):
    ensure_collection(collection_name)
    client = get_milvus_client()
    vectors = await embed_documents(contents)
    if metadatas is None:
        metadatas = [{} for _ in contents]
    if chunk_ids is None:
        chunk_ids = [f"chunk_{i}" for i in range(len(contents))]
    data = []
    for i in range(len(contents)):
        data.append({
            "chunk_id": chunk_ids[i],
            "content": contents[i],
            "metadata": metadatas[i],
            "vector": vectors[i],
        })
    client.insert(collection_name=collection_name, data=data)


async def search(
    collection_name: str,
    query: str,
    top_k: int = 20,
    filter_expr: Optional[str] = None,
) -> list[dict]:
    ensure_collection(collection_name)
    client = get_milvus_client()
    query_vector = await embed_query(query)
    results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=top_k,
        output_fields=["chunk_id", "content", "metadata"],
        filter=filter_expr,
    )
    documents = []
    if results and len(results) > 0:
        for hit in results[0]:
            documents.append({
                "content": hit["entity"]["content"],
                "chunk_id": hit["entity"]["chunk_id"],
                "metadata": hit["entity"]["metadata"],
                "score": hit["distance"],
            })
    return documents


async def hybrid_search(
    collection_name: str,
    query: str,
    top_k: int = 20,
    bm25_results: Optional[list[dict]] = None,
    alpha: float = 0.7,
) -> list[dict]:
    vector_results = await search(collection_name, query, top_k=top_k)
    if bm25_results is None:
        return vector_results
    combined = {}
    for doc in vector_results:
        key = doc["chunk_id"]
        combined[key] = {
            **doc,
            "vector_score": doc["score"],
            "bm25_score": 0.0,
        }
    for doc in bm25_results:
        key = doc["chunk_id"]
        if key in combined:
            combined[key]["bm25_score"] = doc["score"]
        else:
            combined[key] = {
                **doc,
                "vector_score": 0.0,
                "bm25_score": doc["score"],
            }
    for key in combined:
        doc = combined[key]
        max_v = max(d["vector_score"] for d in combined.values()) or 1.0
        max_b = max(d["bm25_score"] for d in combined.values()) or 1.0
        v_norm = doc["vector_score"] / max_v
        b_norm = doc["bm25_score"] / max_b
        doc["combined_score"] = alpha * v_norm + (1 - alpha) * b_norm
    sorted_results = sorted(combined.values(), key=lambda x: x["combined_score"], reverse=True)
    return sorted_results[:top_k]


def delete_collection(collection_name: str):
    client = get_milvus_client()
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)


def get_collection_stats(collection_name: str) -> dict:
    client = get_milvus_client()
    if not client.has_collection(collection_name):
        return {"exists": False}
    stats = client.get_collection_stats(collection_name)
    return {"exists": True, "row_count": stats.get("row_count", 0)}


async def delete_documents_by_metadata(
    collection_name: str,
    metadata_filter: dict,
):
    client = get_milvus_client()
    if not client.has_collection(collection_name):
        return

    filter_parts = []
    for key, value in metadata_filter.items():
        if isinstance(value, str):
            filter_parts.append(f'metadata["{key}"] == "{value}"')
        elif isinstance(value, (int, float)):
            filter_parts.append(f'metadata["{key}"] == {value}')
        elif isinstance(value, bool):
            filter_parts.append(f'metadata["{key}"] == {str(value).lower()}')

    if filter_parts:
        filter_expr = " and ".join(filter_parts)
        client.delete(
            collection_name=collection_name,
            filter=filter_expr,
        )
