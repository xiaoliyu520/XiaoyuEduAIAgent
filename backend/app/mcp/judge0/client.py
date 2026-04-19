import httpx
from typing import Optional
from app.core.config import get_settings
from app.common.exceptions import CodeSandboxException

settings = get_settings()

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


async def execute_code(
    code: str,
    language: str = "python",
    stdin: str = "",
    timeout: int = 10,
    memory_limit: int = 128000,
) -> dict:
    language_id = LANGUAGE_MAP.get(language.lower(), 71)
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
        raise CodeSandboxException(f"代码沙箱请求失败: {str(e)}")
    except Exception as e:
        raise CodeSandboxException(f"代码沙箱执行异常: {str(e)}")


async def get_languages() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.JUDGE0_API_URL}/languages")
            response.raise_for_status()
            return response.json()
    except Exception:
        return [
            {"id": v, "name": k}
            for k, v in LANGUAGE_MAP.items()
        ]
