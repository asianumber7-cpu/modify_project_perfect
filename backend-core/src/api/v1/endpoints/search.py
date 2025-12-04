import logging
import base64
import asyncio # [추가] 재시도 대기(sleep)를 위해 필요
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from pydantic import ValidationError 

from src.api import deps
from src.crud.crud_product import crud_product
from src.schemas.product import ProductResponse
from src.models.product import Product
from src.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

def detect_gender_intent(query: str) -> Optional[str]:
    """검색어에서 성별 키워드 추출"""
    q = query.lower()
    if any(x in q for x in ["남자", "남성", "맨", "men", "male", "boy"]):
        return "Male"
    elif any(x in q for x in ["여자", "여성", "우먼", "women", "female", "girl"]):
        return "Female"
    return None

@router.post("/ai-search", response_model=Dict[str, Any])
async def ai_search(
    query: str = Form(..., description="사용자 검색 쿼리"),
    image_file: Optional[UploadFile] = File(None),
    limit: int = Form(10),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    통합 AI 기반 상품 검색 (Retry Logic & Gender Filter 적용)
    """
    logger.info(f"Received search query: '{query}' with image: {image_file is not None}")

    # 1. 성별 필터 추출
    target_gender = detect_gender_intent(query)
    if target_gender:
        logger.info(f"🔍 Gender Intent Detected: {target_gender}")

    # 2. 이미지 처리
    image_b64: Optional[str] = None
    if image_file:
        try:
            content = await image_file.read()
            image_b64 = base64.b64encode(content).decode("utf-8")
        except Exception as e:
            logger.error(f"Image file read error: {e}")
            raise HTTPException(status_code=400, detail="이미지 파일을 읽을 수 없습니다.")

    # 3. AI Service 호출 (Retry Logic 적용)
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    search_path = 'INTERNAL'
    reason = "AI 검색 결과입니다."
    vector: List[float] = []
    
    # 최대 3번 재시도
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # A. 경로 결정 (Orchestrator)
                try:
                    # [FIX] 중복 경로 제거 (/api/v1 삭제)
                    # AI_SERVICE_API_URL에 이미 /api/v1이 포함되어 있습니다.
                    path_response = await client.post(
                        f"{AI_SERVICE_API_URL}/determine-path", 
                        json={"query": query}
                    )
                    if path_response.status_code == 200:
                        search_path = path_response.json().get("path", 'INTERNAL')
                except Exception as e:
                    # 경로 결정 실패는 치명적이지 않음 -> 기본값 사용
                    logger.warning(f"Path determination skipped: {e}")

                # B. AI 처리 및 벡터 생성
                ai_endpoint = "/process-external" if search_path == 'EXTERNAL' else "/process-internal"
                ai_payload = {"query": query, "image_b64": image_b64}
                
                # [FIX] 중복 경로 제거
                ai_data_response = await client.post(
                    f"{AI_SERVICE_API_URL}{ai_endpoint}", 
                    json=ai_payload
                )
                
                if ai_data_response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"AI Error {ai_data_response.status_code}", 
                        request=ai_data_response.request, 
                        response=ai_data_response
                    )

                ai_data = ai_data_response.json()
                vector = ai_data.get("vector", [])
                reason = ai_data.get("reason", reason)
                
                # 성공하면 루프 탈출
                break

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as e:
            logger.warning(f"⚠️ AI Connection failed (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                # 마지막 시도까지 실패하면 에러 발생
                logger.error(f"AI Connection critical error: All connection attempts failed")
                raise HTTPException(status_code=503, detail="AI 서비스 연결 실패 (잠시 후 다시 시도해주세요)")
            
            # 재시도 전 잠시 대기 (1초)
            await asyncio.sleep(1)

    # 4. 벡터 유효성 검사
    if not vector:
        raise HTTPException(status_code=500, detail="AI 벡터 생성 실패 (Empty Vector)")

    # 5. DB 검색 (Gender Filter 적용)
    try:
        results: List[Product] = await crud_product.search_by_vector(
            db, 
            query_vector=vector, 
            limit=limit,
            threshold=1.2,
            filter_gender=target_gender 
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 벡터 검색 오류")

    # 6. 결과 반환
    product_responses = []
    
    for p in results:
        clean_name = p.name
        if not clean_name or len(str(clean_name).strip()) < 2:
            clean_name = "이름 미정 상품"
        
        try:
            p_dict = {
                "id": p.id,
                "name": clean_name,
                "description": p.description or "",
                "price": p.price or 0,
                "stock_quantity": p.stock_quantity or 0,
                "category": p.category or "Etc",
                "image_url": p.image_url,
                "embedding": p.embedding,
                "gender": p.gender,
                "is_active": p.is_active,
                "created_at": p.created_at,
                "updated_at": p.updated_at
            }
            product_responses.append(ProductResponse.model_validate(p_dict))
            
        except ValidationError as e:
            logger.warning(f"⚠️ Skipping invalid product ID {p.id}: {e}")
            continue
    
    return {
        "status": "SUCCESS",
        "answer": reason,
        "products": product_responses,
        "search_path": search_path
    }