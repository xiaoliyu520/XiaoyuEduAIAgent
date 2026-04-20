import os
from typing import Optional
import numpy as np
from app.core.config import get_settings

settings = get_settings()

_model: Optional[any] = None
_type_embeddings: Optional[dict] = None

QUERY_TYPE_DESCRIPTIONS = {
    "chitchat": [
        "你好",
        "您好",
        "早上好",
        "晚上好",
        "再见",
        "拜拜",
        "谢谢",
        "感谢",
        "不好意思",
        "抱歉",
        "你是谁",
        "你叫什么",
        "你是机器人吗",
        "怎么样",
        "好吗",
        "行吗",
        "可以吗",
        "你好呀",
        "嗨",
        "哈喽",
    ],
    "clear": [
        "什么是机器学习",
        "Python中list和tuple的区别是什么",
        "如何使用面向对象编程",
        "解释一下数据库索引",
        "什么是RESTful API",
        "如何配置环境变量",
        "解释一下这个概念",
        "这个函数怎么用",
        "什么是设计模式",
        "如何优化SQL查询",
        "解释一下HTTP协议",
        "什么是微服务架构",
    ],
    "vague": [
        "那个怎么用",
        "关于机器学习的东西",
        "老师讲的那个方法",
        "之前说的那个问题",
        "这个东西是什么",
        "那个功能怎么实现",
        "刚才提到的那个",
        "这个怎么弄",
        "那个怎么搞",
        "关于这个的一些问题",
    ],
    "broad": [
        "介绍一下深度学习",
        "如何学好编程",
        "Web开发都需要学什么",
        "讲讲微服务",
        "说说数据库优化",
        "介绍一下Spring框架",
        "如何设计系统架构",
        "讲讲前端技术栈",
        "介绍一下DevOps",
        "如何进行性能优化",
    ],
}


def _get_model():
    global _model
    if _model is None:
        try:
            if settings.HF_MIRROR_URL:
                os.environ["HF_ENDPOINT"] = settings.HF_MIRROR_URL
            
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.INTENT_CLASSIFIER_MODEL)
        except Exception as e:
            raise RuntimeError(f"问题类型分类模型加载失败: {str(e)}")
    return _model


def _get_type_embeddings():
    global _type_embeddings
    if _type_embeddings is None:
        model = _get_model()
        _type_embeddings = {}
        for query_type, descriptions in QUERY_TYPE_DESCRIPTIONS.items():
            embeddings = model.encode(descriptions, convert_to_numpy=True)
            _type_embeddings[query_type] = embeddings
    return _type_embeddings


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def classify_query_type(query: str) -> tuple[str, float]:
    try:
        model = _get_model()
        type_embeddings = _get_type_embeddings()
        
        query_embedding = model.encode([query], convert_to_numpy=True)[0]
        
        scores = {}
        for query_type, embeddings in type_embeddings.items():
            similarities = [_cosine_similarity(query_embedding, emb) for emb in embeddings]
            scores[query_type] = sum(similarities) / len(similarities)
        
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        return best_type, best_score
    except Exception as e:
        return "clear", 0.0


async def async_classify_query_type(query: str) -> tuple[str, float]:
    return classify_query_type(query)
