import asyncio
from celery import Celery
from sqlalchemy import select
from src.config.settings import settings
from src.db.session import async_session_maker # 세션 메이커 필요
from src.models.user import User
from src.services.email_service import send_email_async

# Celery 설정
celery_app = Celery(
    "modify_backend_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
)

@celery_app.task(name="tasks.broadcast_email")
def broadcast_email_task(subject: str, body: str, filter_type: str = "all"):
    """
    백그라운드에서 실행되는 메일 발송 Task
    """
    async def _process_email_sending():
        async with async_session_maker() as session:
            # 1. 대상 유저 조회
            query = select(User.email).where(User.is_active == True)
            # 추후 is_marketing_agreed 필드가 생기면 여기서 필터링 추가

            if filter_type == "marketing":
                # 마케팅 수신 동의한 사람만 필터링
                query = query.where(User.is_marketing_agreed == True)
            
            result = await session.execute(query)
            emails = [row[0] for row in result.all()]
            
            if not emails:
                return f"No recipients found for filter: {filter_type}"

            # 2. 배치 단위로 나누어 발송 (예: 50명씩) - SMTP 서버 제한 고려
            batch_size = 50
            for i in range(0, len(emails), batch_size):
                batch_emails = emails[i:i + batch_size]
                await send_email_async(batch_emails, subject, body)
                
            return f"Sent emails to {len(emails)} users."

    # Async 함수를 Sync 환경(Celery)에서 실행
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_process_email_sending())