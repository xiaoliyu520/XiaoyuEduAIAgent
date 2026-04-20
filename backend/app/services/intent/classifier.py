import os
from typing import Optional
from enum import Enum
import numpy as np
from app.core.config import get_settings
from app.common.exceptions import IntentClassificationException

settings = get_settings()


class AgentType(str, Enum):
    QA = "qa"
    RESUME = "resume"
    INTERVIEW = "interview"
    CODE = "code"


INTENT_LABEL_NAMES_ZH = {
    AgentType.QA: "智能问答",
    AgentType.RESUME: "简历审查",
    AgentType.INTERVIEW: "模拟面试",
    AgentType.CODE: "代码检查",
}

INTENT_DESCRIPTIONS = {
    AgentType.QA: [
        "我想问一个问题",
        "什么是机器学习",
        "请解释一下Python",
        "这个知识点是什么意思",
        "帮我解答一个问题",
        "课程内容讲解",
        "学习资料查询",
        "技术概念解释",
    ],
    AgentType.RESUME: [
        "帮我看看简历",
        "审查一下我的简历",
        "简历有什么问题",
        "优化我的简历",
        "简历修改建议",
        "检查简历格式",
        "简历内容评估",
    ],
    AgentType.INTERVIEW: [
        "模拟面试",
        "我想练习面试",
        "面试模拟",
        "进行一次面试练习",
        "帮我准备面试",
        "面试问题练习",
        "技术面试模拟",
    ],
    AgentType.CODE: [
        "检查我的代码",
        "代码有什么问题",
        "帮我调试代码",
        "优化这段代码",
        "代码审查",
        "找出代码bug",
        "代码质量检查",
    ],
}

_model: Optional[any] = None
_intent_embeddings: Optional[dict] = None


def _get_model():
    global _model
    if _model is None:
        try:
            if settings.HF_MIRROR_URL:
                os.environ["HF_ENDPOINT"] = settings.HF_MIRROR_URL
            
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.INTENT_CLASSIFIER_MODEL)
        except Exception as e:
            raise IntentClassificationException(f"意图分类模型加载失败: {str(e)}")
    return _model


def _get_intent_embeddings():
    global _intent_embeddings
    if _intent_embeddings is None:
        model = _get_model()
        _intent_embeddings = {}
        for agent_type, descriptions in INTENT_DESCRIPTIONS.items():
            embeddings = model.encode(descriptions, convert_to_numpy=True)
            _intent_embeddings[agent_type] = embeddings
    return _intent_embeddings


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def classify_intent(query: str) -> AgentType:
    try:
        model = _get_model()
        intent_embeddings = _get_intent_embeddings()
        
        query_embedding = model.encode([query], convert_to_numpy=True)[0]
        
        best_intent = AgentType.QA
        best_score = -1.0
        
        for agent_type, embeddings in intent_embeddings.items():
            scores = [_cosine_similarity(query_embedding, emb) for emb in embeddings]
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_intent = agent_type
        
        return best_intent
    except Exception as e:
        raise IntentClassificationException(f"意图分类失败: {str(e)}")
