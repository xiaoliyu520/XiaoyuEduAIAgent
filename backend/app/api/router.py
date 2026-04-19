from fastapi import APIRouter

router = APIRouter()

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.agents import router as agents_router

router.include_router(auth_router, prefix="/v1")
router.include_router(chat_router, prefix="/v1")
router.include_router(knowledge_router, prefix="/v1")
router.include_router(agents_router, prefix="/v1")
