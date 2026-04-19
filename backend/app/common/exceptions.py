from fastapi import HTTPException, status


class AgentException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=detail)


class LLMException(AgentException):
    def __init__(self, detail: str = "LLM调用失败"):
        super().__init__(detail=detail, status_code=status.HTTP_502_BAD_GATEWAY)


class KnowledgeBaseException(AgentException):
    def __init__(self, detail: str = "知识库操作失败"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class IntentClassificationException(AgentException):
    def __init__(self, detail: str = "意图分类失败"):
        super().__init__(detail=detail, status_code=status.HTTP_502_BAD_GATEWAY)


class CodeSandboxException(AgentException):
    def __init__(self, detail: str = "代码沙箱执行失败"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class AuthenticationException(HTTPException):
    def __init__(self, detail: str = "认证失败"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class PermissionException(HTTPException):
    def __init__(self, detail: str = "权限不足"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
