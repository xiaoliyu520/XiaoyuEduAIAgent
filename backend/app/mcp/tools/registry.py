from langchain_core.tools import tool
from app.mcp.milvus.client import search as milvus_search, hybrid_search as milvus_hybrid_search
from app.mcp.milvus.bm25 import get_bm25_index
from app.mcp.judge0.client import execute_code, get_languages


@tool
async def knowledge_search(query: str, collection_name: str = "default", top_k: int = 20) -> str:
    """在知识库中检索相关文档。query为检索问题，collection_name为知识库集合名称，top_k为返回结果数量。"""
    results = await milvus_search(collection_name, query, top_k)
    if not results:
        return "未找到相关文档"
    output = []
    for i, doc in enumerate(results):
        output.append(f"[{i+1}] (相关度: {doc['score']:.3f}) {doc['content']}")
    return "\n\n".join(output)


@tool
async def knowledge_hybrid_search(query: str, collection_name: str = "default", top_k: int = 20) -> str:
    """在知识库中进行混合检索（向量+BM25），效果优于单一检索。query为检索问题。"""
    bm25 = get_bm25_index()
    bm25_results = bm25.search(collection_name, query, top_k=top_k) if bm25.has_index(collection_name) else None
    results = await milvus_hybrid_search(collection_name, query, top_k=top_k, bm25_results=bm25_results)
    if not results:
        return "未找到相关文档"
    output = []
    for i, doc in enumerate(results):
        output.append(f"[{i+1}] (综合分: {doc.get('combined_score', doc.get('score', 0)):.3f}) {doc['content']}")
    return "\n\n".join(output)


@tool
async def run_code(code: str, language: str = "python") -> str:
    """在沙箱中执行代码并返回结果。code为代码内容，language为编程语言。"""
    result = await execute_code(code, language)
    status = result["status"]
    output_parts = [f"执行状态: {status}"]
    if result.get("compile_output"):
        output_parts.append(f"编译输出: {result['compile_output']}")
    if result.get("stdout"):
        output_parts.append(f"标准输出: {result['stdout']}")
    if result.get("stderr"):
        output_parts.append(f"错误输出: {result['stderr']}")
    output_parts.append(f"执行时间: {result.get('time', '0')}s")
    output_parts.append(f"内存使用: {result.get('memory', 0)}KB")
    return "\n".join(output_parts)


@tool
async def list_languages() -> str:
    """列出Judge0沙箱支持的编程语言。"""
    languages = await get_languages()
    return "\n".join([f"{lang['id']}: {lang['name']}" for lang in languages])


ALL_TOOLS = [knowledge_search, knowledge_hybrid_search, run_code, list_languages]
