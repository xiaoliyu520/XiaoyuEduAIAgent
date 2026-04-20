import httpx
import logging
from typing import Optional
from app.core.config import get_settings
from app.common.exceptions import CodeSandboxException

settings = get_settings()
logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "python": 71,
    "javascript": 63,
    "java": 62,
    "cpp": 54,
    "c": 50,
    "go": 60,
    "rust": 73,
    "typescript": 74,
}

LANGUAGE_NAMES = {
    "python": "Python 3",
    "javascript": "JavaScript (Node.js)",
    "java": "Java",
    "cpp": "C++",
    "c": "C",
    "go": "Go",
    "rust": "Rust",
    "typescript": "TypeScript",
}


async def check_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.JUDGE0_API_URL}/system_info")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Judge0服务健康检查通过: {data}")
            return {
                "status": "healthy",
                "info": data,
            }
    except Exception as e:
        logger.warning(f"Judge0服务健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def execute_code(
    code: str,
    language: str = "python",
    stdin: str = "",
    timeout: int = 10,
    memory_limit: int = 128000,
) -> dict:
    language_id = LANGUAGE_MAP.get(language.lower(), 71)
    
    logger.debug(f"执行代码请求: language={language}, language_id={language_id}, code_length={len(code)}")
    
    payload = {
        "source_code": code,
        "language_id": language_id,
        "stdin": stdin,
        "cpu_time_limit": timeout,
        "memory_limit": memory_limit,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.JUDGE0_API_URL}/submissions?base64_encoded=false&wait=true",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"代码执行结果: status_id={result.get('status', {}).get('id')}, time={result.get('time')}, memory={result.get('memory')}")
            
            return {
                "status": result.get("status", {}).get("description", "Unknown"),
                "status_id": result.get("status", {}).get("id", 0),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "compile_output": result.get("compile_output", ""),
                "exit_code": result.get("exit_code", 0),
                "time": result.get("time", "0"),
                "memory": result.get("memory", 0),
            }
    except httpx.HTTPError as e:
        logger.error(f"代码沙箱请求失败: {e}")
        raise CodeSandboxException(f"代码沙箱请求失败: {str(e)}")
    except Exception as e:
        logger.error(f"代码沙箱执行异常: {e}")
        raise CodeSandboxException(f"代码沙箱执行异常: {str(e)}")


async def get_languages() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.JUDGE0_API_URL}/languages")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning(f"获取语言列表失败，使用本地列表: {e}")
        return [
            {"id": v, "name": LANGUAGE_NAMES.get(k, k)}
            for k, v in LANGUAGE_MAP.items()
        ]


def get_supported_languages() -> list[dict]:
    return [
        {"id": v, "name": LANGUAGE_NAMES.get(k, k), "code": k}
        for k, v in LANGUAGE_MAP.items()
    ]
