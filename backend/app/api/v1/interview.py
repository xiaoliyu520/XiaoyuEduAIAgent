from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.database import User, Resume, Conversation, InterviewReport
from app.models.schemas import ResponseBase, InterviewStartRequest
from app.api.deps import get_current_user
from app.agents.interview.agent import InterviewAgent

router = APIRouter(prefix="/interview", tags=["模拟面试"])


@router.post("/start", response_model=ResponseBase)
async def start_interview(
    data: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume_summary = ""
    if data.resume_id:
        result = await db.execute(
            select(Resume).where(Resume.id == data.resume_id, Resume.user_id == current_user.id)
        )
        resume = result.scalar_one_or_none()
        if resume:
            resume_summary = resume.raw_text[:2000]

    conversation = Conversation(
        user_id=current_user.id,
        agent_type="interview",
        title="模拟面试",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    agent = InterviewAgent()
    state = {
        "query": "开始面试",
        "context": {
            "resume_summary": resume_summary,
            "stage": "INTRO",
            "focus_areas": data.focus_areas or [],
        },
        "messages": [],
        "conversation_id": conversation.id,
        "user_id": current_user.id,
        "agent_type": "interview",
        "intermediate_results": [],
        "final_answer": "",
        "confidence": 0.0,
        "metadata": {},
        "error": None,
    }
    agent_result = await agent.run(state)

    return ResponseBase(data={
        "conversation_id": conversation.id,
        "message": agent_result.get("final_answer", ""),
        "stage": "INTRO",
    })


@router.post("/respond", response_model=ResponseBase)
async def interview_respond(
    conversation_id: int,
    message: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("面试会话不存在")

    agent = InterviewAgent()
    state = {
        "query": message,
        "context": {},
        "messages": [],
        "conversation_id": conversation_id,
        "user_id": current_user.id,
        "agent_type": "interview",
        "intermediate_results": [],
        "final_answer": "",
        "confidence": 0.0,
        "metadata": {},
        "error": None,
    }
    agent_result = await agent.run(state)

    stage = agent_result.get("context", {}).get("stage", "TECH")
    report = agent_result.get("context", {}).get("report")

    if report and stage == "REPORT":
        interview_report = InterviewReport(
            user_id=current_user.id,
            conversation_id=conversation_id,
            tech_score=report.get("tech_score", 0),
            expression_score=report.get("expression_score", 0),
            overall_score=report.get("overall_score", 0),
            radar_data=json.dumps(report.get("radar_data", {}), ensure_ascii=False),
            report_content=agent_result.get("final_answer", ""),
            suggestions=json.dumps(report.get("suggestions", []), ensure_ascii=False),
        )
        db.add(interview_report)
        await db.commit()

    return ResponseBase(data={
        "conversation_id": conversation_id,
        "message": agent_result.get("final_answer", ""),
        "stage": stage,
        "report": report if stage == "REPORT" else None,
    })
