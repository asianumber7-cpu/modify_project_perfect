import redis
import logging
from datetime import datetime
from typing import Tuple
from src.core.config import settings # 설정 파일에서 값들을 가져오기 위해 임포트

logger = logging.getLogger(__name__)

class QuotaMonitor:
    """
    Google Search API 호출 쿼터를 Redis를 사용하여 실시간으로 관리하는 클래스입니다.
    """
    def __init__(self):
        # Redis 연결 정보는 settings.py에서 가져옵니다.
        self.redis = redis.Redis(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT, 
            db=0, 
            decode_responses=True
        )
        logger.info(f"QuotaMonitor initialized. Redis Host: {settings.REDIS_HOST}")

    def check_and_increment(self) -> Tuple[bool, int]:
        """
        Google API 일일 할당량을 체크하고 사용량을 증가시킵니다.
        Returns: (사용가능여부, 남은횟수)
        """
        if settings.GOOGLE_API_DAILY_QUOTA <= 0:
            # 쿼터가 0 이하라면 무제한으로 간주 (또는 기능 비활성화)
            return True, 9999 
            
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"google_api_quota:{today}"
        
        # Redis 트랜잭션 사용
        with self.redis.pipeline() as pipe:
            pipe.get(key)
            results = pipe.execute()
            
            current_usage = int(results[0]) if results[0] else 0
            
            if current_usage >= settings.GOOGLE_API_DAILY_QUOTA:
                logger.warning(f"⚠️ Google API Quota Exceeded! Used: {current_usage}/{settings.GOOGLE_API_DAILY_QUOTA}")
                return False, 0
                
            # 사용량 증가 및 TTL 설정 (24시간 + 여유분 1시간 = 86400 + 3600초)
            pipe.incr(key)
            pipe.expire(key, 86400 + 3600) 
            new_usage = pipe.execute()[0]
            
            remaining = settings.GOOGLE_API_DAILY_QUOTA - new_usage
            
            return True, remaining

quota_monitor = QuotaMonitor()