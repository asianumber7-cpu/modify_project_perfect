import hashlib
import json
import logging
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.config.settings import settings

# 로깅 설정
logger = logging.getLogger("vector_search")

# Redis 클라이언트 (Connection Pool 활용)
redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

async def search_similar_products(db: AsyncSession, embedding: list[float], limit: int = 10):
    """
    pgvector 검색 + Redis Caching Layer
    """
    # 1. Cache Key 생성 (MD5 of embedding + limit)
    # embedding 리스트는 부동소수점이므로 문자열 변환 후 해싱
    emb_str = json.dumps(embedding)
    emb_hash = hashlib.md5(emb_str.encode()).hexdigest()
    cache_key = f"vector_search:{emb_hash}:{limit}"
    
    # 2. Redis Cache 조회
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        logger.info(f"🟢 Cache Hit: {cache_key}")
        return json.loads(cached_result)
    
    logger.info(f"🔴 Cache Miss: {cache_key} -> Querying DB")

    # 3. DB Query (Cache Miss)
    query = text("""
        SELECT id, name, price, image_url, 1 - (embedding <=> :embedding) as similarity
        FROM products
        WHERE deleted_at IS NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)
    
    embedding_pg_format = str(embedding)
    result = await db.execute(query, {"embedding": embedding_pg_format, "limit": limit})
    rows = result.mappings().all()
    
    # dict 형태로 변환 (JSON 직렬화를 위해)
    response_data = [dict(row) for row in rows]
    
    # 4. Redis Cache 저장 (TTL 10분 = 600초)
    await redis_client.setex(cache_key, 600, json.dumps(response_data))
    
    return response_data

def should_trigger_rag(query: str, internal_count: int) -> bool:
    keywords = ["트렌드", "유행", "인스타", "최신", "연예인", "아이유", "실제", "요즘", "셀럽"]
    
    if any(k in query for k in keywords):
        return True
    if internal_count < 3:
        return True
    # 명시적 요청 ("RAG" 등의 접두어가 붙은 경우 로직 추가 가능)
        
    return False