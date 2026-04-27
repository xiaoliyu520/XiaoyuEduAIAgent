from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.redis import close_redis
from app.api.router import router

settings = get_settings()
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


async def preload_models():
    """预加载模型"""
    try:
        from app.services.intent.query_type import preload_model
        preload_model()
    except Exception as e:
        logger.warning(f"模型预加载失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.DEBUG and settings.JWT_SECRET_KEY == "change-me-in-production":
        logger.warning("JWT_SECRET_KEY is default value, please change it in production!")
    
    await init_db()
    
    preload_task = asyncio.create_task(asyncio.to_thread(preload_models))
    
    yield
    
    preload_task.cancel()
    await close_db()
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    checks = {"status": "healthy", "services": {}}

    try:
        from app.core.database import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(select(1))
        checks["services"]["postgresql"] = "healthy"
    except Exception as e:
        checks["services"]["postgresql"] = f"unhealthy: {e}"
        checks["status"] = "degraded"

    try:
        from app.core.redis import get_redis_client
        redis_client = await get_redis_client()
        await redis_client.ping()
        checks["services"]["redis"] = "healthy"
    except Exception as e:
        checks["services"]["redis"] = f"unhealthy: {e}"
        checks["status"] = "degraded"

    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        client.list_collections()
        checks["services"]["milvus"] = "healthy"
    except Exception as e:
        checks["services"]["milvus"] = f"unhealthy: {e}"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"code": 1, "message": str(exc), "data": None})


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    message = "服务器内部错误" if not settings.DEBUG else f"服务器内部错误: {str(exc)}"
    return JSONResponse(
        status_code=500,
        content={"code": 1, "message": message, "data": None},
    )
