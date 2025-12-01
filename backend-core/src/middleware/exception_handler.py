import time
from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from src.config.settings import settings

async def global_exception_handler(request: Request, exc: Exception):
    """
    모든 예외를 표준화된 JSON 형식으로 변환합니다.
    Production 환경에서는 내부 스택 트레이스를 숨깁니다.
    """
    error_code = "INTERNAL_SERVER_ERROR"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "An unexpected error occurred."
    
    if isinstance(exc, SQLAlchemyError):
        error_code = "DB_ERROR"
        message = "Database operation failed."
        # 실제 운영시에는 로그 시스템(Sentry 등)으로 전송 필요
    
    # 상세 에러 정보 (Dev 환경에서만 노출)
    details = str(exc) if settings.DEBUG else None
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "details": details,
            "timestamp": time.time(),
            "path": request.url.path
        }
    )