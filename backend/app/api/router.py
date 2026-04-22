from fastapi import APIRouter

router = APIRouter()

from app.api.v1.auth import router as auth_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.qa import router as qa_router
from app.api.v1.code import router as code_router
from app.api.v1.resume import router as resume_router
from app.api.v1.interview import router as interview_router

router.include_router(auth_router, prefix="/v1")
router.include_router(knowledge_router, prefix="/v1")
router.include_router(qa_router, prefix="/v1")
router.include_router(code_router, prefix="/v1")
router.include_router(resume_router, prefix="/v1")
router.include_router(interview_router, prefix="/v1")
