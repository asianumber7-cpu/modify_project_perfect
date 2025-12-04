# backend-core/src/services/vector_search.py

import hashlib
import json
import logging
import re
from typing import Optional, Dict, Any
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.config.settings import settings

# 로깅 설정
logger = logging.getLogger("vector_search")

# Redis 클라이언트
redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

def extract_filters_from_text(query_text: str) -> Dict[str, Any]:
    """
    사용자 자연어 쿼리에서 성별 등 메타데이터 필터를 추출하는 룰 베이스 로직.
    추후 AI가 JSON으로 추출해준다면 이 함수는 대체될 수 있습니다.
    """
    filters = {}
    
    # 성별 감지 로직
    if any(word in query_text for word in ["남자", "남성", "맨", "men", "male"]):
        filters['gender'] = 'Male'
    elif any(word in query_text for word in ["여자", "여성", "우먼", "women", "female"]):
        filters['gender'] = 'Female'
    
    # 여기에 카테고리 등 추가 추출 로직 확장 가능
    
    return filters

async def search_similar_products(
    db: AsyncSession, 
    embedding: list[float], 
    query_text: str = "",  # [NEW] 텍스트 기반 필터링을 위해 쿼리 텍스트 수신
    limit: int = 10
):
    """
    Hybrid Search: Vector Similarity + Metadata Filtering (Gender, etc.)
    """
    # 1. 쿼리 텍스트에서 필터 추출
    filters = extract_filters_from_text(query_text) if query_text else {}
    gender_filter = filters.get('gender')

    # 2. Cache Key 생성 (Embedding Hash + Filters + Limit)
    # 필터 조건이 다르면 캐시 키도 달라야 함 (남자 검색결과 != 여자 검색결과)
    emb_str = json.dumps(embedding)
    emb_hash = hashlib.md5(emb_str.encode()).hexdigest()
    
    # 캐시 키에 성별 필터 포함
    cache_key_parts = [f"vector_search:{emb_hash}", f"limit:{limit}"]
    if gender_filter:
        cache_key_parts.append(f"gender:{gender_filter}")
        
    cache_key = ":".join(cache_key_parts)
    
    # 3. Redis Cache 조회
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        logger.info(f"🟢 Cache Hit: {cache_key}")
        return json.loads(cached_result)
    
    logger.info(f"🔴 Cache Miss: {cache_key} (Filter: {gender_filter}) -> Querying DB")

    # 4. Dynamic SQL Query Construction (동적 쿼리 생성)
    # 기본 쿼리
    base_sql = """
        SELECT id, name, price, image_url, category, gender, 1 - (embedding <=> :embedding) as similarity
        FROM products
        WHERE deleted_at IS NULL
    """
    
    params = {"embedding": str(embedding), "limit": limit}

    # [Core Logic] 성별 필터가 있으면 WHERE 절에 추가
    # 'Unisex'는 남녀 모두에게 노출되어야 하므로 OR 조건 처리
    if gender_filter:
        base_sql += " AND (gender = :gender OR gender = 'Unisex' OR gender IS NULL)"
        params['gender'] = gender_filter

    # 정렬 및 제한
    base_sql += " ORDER BY embedding <=> :embedding LIMIT :limit"

    # 5. Execute DB Query
    result = await db.execute(text(base_sql), params)
    rows = result.mappings().all()
    
    # dict 형태로 변환
    response_data = [dict(row) for row in rows]
    
    # 6. Redis Cache 저장 (TTL 10분)
    await redis_client.setex(cache_key, 600, json.dumps(response_data))
    
    return response_data

def should_trigger_rag(query: str, internal_count: int) -> bool:
    keywords = ["트렌드", "유행", "인스타", "최신", "연예인", "아이유", "실제", "요즘", "셀럽", "추천", "코디"]
    
    if any(k in query for k in keywords):
        return True
    if internal_count < 3:
        return True
        
    return False