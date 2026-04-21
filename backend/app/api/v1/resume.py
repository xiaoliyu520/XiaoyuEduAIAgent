import logging
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import get_settings
from app.models.database import User, Resume
from app.models.schemas import ResponseBase, ResumeReviewRequest
from app.api.deps import get_current_user
from app.core.minio import upload_file
from app.agents.resume.agent import ResumeAgent
from app.services.document_loaders import DocumentLoader

router = APIRouter(prefix="/resume", tags=["简历审查"])
logger = logging.getLogger(__name__)


@router.get("/list")
async def get_resume_list(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
    )
    resumes = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "file_path": r.file_path,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "has_review": bool(r.review_result),
            "text_length": len(r.raw_text) if r.raw_text else 0,
        }
        for r in resumes
    ]


@router.get("/{resume_id}")
async def get_resume_detail(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        return {"error": "简历不存在"}
    
    radar_data = {}
    if resume.radar_data:
        try:
            radar_data = json.loads(resume.radar_data)
        except:
            pass
    
    return {
        "id": resume.id,
        "file_path": resume.file_path,
        "raw_text": resume.raw_text,
        "review_result": resume.review_result,
        "radar_data": radar_data,
        "created_at": resume.created_at.isoformat() if resume.created_at else None,
    }


@router.post("/upload", response_model=ResponseBase)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Uploading resume: {file.filename}, content_type: {file.content_type}")

    file_data = await file.read()
    logger.info(f"File size: {len(file_data)} bytes")

    object_name = f"resumes/{current_user.id}/{file.filename}"
    await upload_file(object_name, file_data, file.content_type or "application/octet-stream")
    logger.info(f"File uploaded to MinIO: {object_name}")

    try:
        raw_text = DocumentLoader.load_from_bytes(file_data, file.filename or "")
        logger.info(f"DocumentLoader extracted {len(raw_text)} characters")
    except Exception as e:
        logger.error(f"DocumentLoader failed: {e}", exc_info=True)
        return ResponseBase(message=f"文档解析失败: {str(e)}", data={"error": str(e)})

    resume = Resume(
        user_id=current_user.id,
        file_path=object_name,
        raw_text=raw_text,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    return ResponseBase(
        data={
            "resume_id": resume.id,
            "filename": file.filename,
            "text_length": len(raw_text),
        }
    )


@router.post("/review/stream")
async def review_resume_stream(
    data: ResumeReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Streaming review for resume: {data.resume_id}")

    result = await db.execute(
        select(Resume).where(Resume.id == data.resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        async def error_gen():
            yield f"data: {json.dumps({'error': '简历不存在'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    resume_raw_text = resume.raw_text
    resume_id = resume.id
    user_id = current_user.id

    async def event_generator():
        agent = ResumeAgent()
        state = {
            "query": resume_raw_text,
            "context": {"resume_text": resume_raw_text},
            "messages": [],
            "conversation_id": 0,
            "user_id": user_id,
            "agent_type": "resume",
            "intermediate_results": [],
            "final_answer": "",
            "confidence": 0.0,
            "metadata": {},
            "error": None,
        }

        full_answer = ""
        try:
            async for chunk in agent.stream(state):
                full_answer += chunk
                event_data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            return

        report = state.get("context", {}).get("report", {})
        radar_data = report.get("radar_data", {}) if report else {}
        logger.info(f"Report from state: {report is not None}")
        logger.info(f"Radar data: {radar_data}")
        
        clean_answer = full_answer
        if "RADAR_JSON:" in clean_answer:
            clean_answer = clean_answer.split("RADAR_JSON:")[0].strip()
        logger.info(f"Clean answer length: {len(clean_answer)}")
        
        async with AsyncSessionLocal() as new_db:
            try:
                result = await new_db.execute(
                    select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
                )
                resume_to_update = result.scalar_one_or_none()
                if resume_to_update:
                    resume_to_update.review_result = clean_answer
                    resume_to_update.radar_data = json.dumps(radar_data, ensure_ascii=False) if radar_data else "{}"
                    await new_db.commit()
                    logger.info(f"Resume {resume_id} saved to database successfully")
                else:
                    logger.error(f"Resume {resume_id} not found in database")
            except Exception as e:
                logger.error(f"Failed to save resume to database: {e}", exc_info=True)
                await new_db.rollback()

        done_data = json.dumps({
            "done": True,
            "report": {"radar_data": radar_data},
        }, ensure_ascii=False)
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


@router.post("/review", response_model=ResponseBase)
async def review_resume(
    data: ResumeReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Reviewing resume: {data.resume_id}")

    result = await db.execute(
        select(Resume).where(Resume.id == data.resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise ValueError("简历不存在")

    agent = ResumeAgent()
    state = {
        "query": resume.raw_text,
        "context": {"resume_text": resume.raw_text},
        "messages": [],
        "conversation_id": 0,
        "user_id": current_user.id,
        "agent_type": "resume",
        "intermediate_results": [],
        "final_answer": "",
        "confidence": 0.0,
        "metadata": {},
        "error": None,
    }
    agent_result = await agent.run(state)

    report = agent_result.get("context", {}).get("report", {})
    resume.review_result = agent_result.get("final_answer", "")
    resume.radar_data = json.dumps(report.get("radar_data", {}), ensure_ascii=False)
    await db.commit()

    logger.info(f"Resume review completed: {data.resume_id}")
    return ResponseBase(data=agent_result.get("final_answer", ""))
