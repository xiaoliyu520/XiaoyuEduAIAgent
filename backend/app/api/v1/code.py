from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.models.database import User
from app.models.schemas import ResponseBase, CodeCheckRequest
from app.api.deps import get_current_user
from app.agents.code.agent import CodeAgent
from app.mcp.judge0.client import get_supported_languages, check_health

router = APIRouter(prefix="/code", tags=["代码检查"])


@router.get("/languages", response_model=ResponseBase)
async def get_languages():
    languages = get_supported_languages()
    return ResponseBase(data=languages)


@router.get("/health", response_model=ResponseBase)
async def get_health():
    health = await check_health()
    return ResponseBase(data=health)


@router.post("/check")
async def check_code(
    data: CodeCheckRequest,
    current_user: User = Depends(get_current_user),
):
    agent = CodeAgent()
    state = {
        "query": data.code,
        "context": {"code": data.code, "language": data.language},
        "messages": [],
        "conversation_id": data.conversation_id or 0,
        "user_id": current_user.id,
        "agent_type": "code",
        "intermediate_results": [],
        "final_answer": "",
        "confidence": 0.0,
        "metadata": {},
        "error": None,
    }
    
    async def event_generator():
        full_answer = ""
        try:
            async for chunk in agent.stream(state):
                full_answer += chunk
                event_data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

        done_data = json.dumps({"done": True}, ensure_ascii=False)
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
