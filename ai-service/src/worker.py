import os
from celery import Celery
from src.core.config import settings

# Celery 앱 인스턴스 생성
# Redis 연결 주소는 settings에서 가져옵니다.
CELERY_BROKER_URL = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"

# 🚨 Celery 앱 이름은 폴더 구조와 일치해야 합니다 (src.worker)
celery_app = Celery(
    "src.worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['src.tasks.rag_task'] # 태스크가 정의된 모듈 포함
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Seoul',
    enable_utc=True,
)

# [주의] 이 파일은 Docker Compose에서 ai-service-worker 컨테이너의 진입점 역할을 합니다.