from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.database import User, Resume, InterviewReport, Conversation
from app.models.schemas import ResponseBase, InterviewStartRequest, CodeCheckRequest
from app.api.deps import get_current_user
from app.core.minio import upload_file
from app.orchestrator.orchestrator import get_orchestrator

router = APIRouter(prefix="/agents", tags=["Agent功能"])


@router.post("/resume/upload", response_model=ResponseBase)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_data = await file.read()
    object_name = f"resumes/{current_user.id}/{file.filename}"
    await upload_file(object_name, file_data, file.content_type or "application/octet-stream")

    raw_text = file_data.decode("utf-8", errors="ignore")

    resume = Resume(
        user_id=current_user.id,
        file_path=object_name,
        raw_text=raw_text,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    return ResponseBase(data={
        "resume_id": resume.id,
        "filename": file.filename,
    })


@router.post("/resume/review", response_model=ResponseBase)
async def review_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise ValueError("简历不存在")

    orchestrator = get_orchestrator()
    agent_result = await orchestrator.dispatch(
        query=resume.raw_text,
        user_id=current_user.id,
        agent_type="resume",
        context={"resume_text": resume.raw_text},
    )

    report = agent_result.get("context", {}).get("report", {})
    resume.review_result = agent_result.get("final_answer", "")
    resume.radar_data = json.dumps(report.get("radar_data", {}), ensure_ascii=False)
    await db.commit()

    return ResponseBase(data=agent_result.get("final_answer", ""))


@router.post("/interview/start", response_model=ResponseBase)
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

    orchestrator = get_orchestrator()
    agent_result = await orchestrator.dispatch(
        query="开始面试",
        user_id=current_user.id,
        conversation_id=conversation.id,
        agent_type="interview",
        context={
            "resume_summary": resume_summary,
            "stage": "INTRO",
            "focus_areas": data.focus_areas or [],
        },
    )

    return ResponseBase(data={
        "conversation_id": conversation.id,
        "message": agent_result.get("final_answer", ""),
        "stage": "INTRO",
    })


@router.post("/interview/respond", response_model=ResponseBase)
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

    orchestrator = get_orchestrator()
    agent_result = await orchestrator.dispatch(
        query=message,
        user_id=current_user.id,
        conversation_id=conversation_id,
        agent_type="interview",
    )

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


@router.post("/code/check", response_model=ResponseBase)
async def check_code(
    data: CodeCheckRequest,
    current_user: User = Depends(get_current_user),
):
    orchestrator = get_orchestrator()
    agent_result = await orchestrator.dispatch(
        query=data.code,
        user_id=current_user.id,
        conversation_id=data.conversation_id,
        agent_type="code",
        context={"code": data.code, "language": data.language},
    )

    return ResponseBase(data=agent_result.get("final_answer", ""))
