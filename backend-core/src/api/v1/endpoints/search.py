import json
import httpx
import base64
import logging
from typing import Optional, List, Dict, Any

# 🚨 [수정] UploadFile 처리를 위해 Form 임포트 필수
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

# 내부 모듈 임포트
from src.api.deps import get_db
from src.crud.crud_product import crud_product 
from src.schemas.product import SearchQuery, ProductResponse 
from src.models.product import Product 

logger = logging.getLogger(__name__)
router = APIRouter()

# AI Service API URL (Docker 내부 통신용)
AI_SERVICE_API_URL = "http://ai-service-api:8000/api/v1" 

@router.post("/ai-search", response_model=Dict[str, Any])
async def ai_search(
    # 🚨 [수정] 프론트엔드 FormData 형식에 맞게 Form(...) 사용
    query: str = Form(..., description="사용자 검색 쿼리"),
    image_file: Optional[UploadFile] = File(None),
    limit: int = Form(10),  # limit도 Form 데이터로 올 수 있으므로 처리
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    통합 AI 기반 상품 검색: 경로 결정 (INTERNAL/EXTERNAL), RAG/Vision 분석 및 벡터 검색을 수행합니다.
    """
    logger.info(f"Received search query: '{query}' with image: {image_file is not None}")

    # 1. 이미지 처리 (Base64 변환)
    image_b64: Optional[str] = None
    if image_file:
        try:
            content = await image_file.read()
            image_b64 = base64.b64encode(content).decode("utf-8")
        except Exception as e:
            logger.error(f"Image file read error: {e}")
            raise HTTPException(status_code=400, detail="이미지 파일을 읽을 수 없습니다.")

    # 2. AI Service 호출 파이프라인
    async with httpx.AsyncClient(timeout=120.0) as client:
        
        # A. 검색 경로 결정 (AI Orchestrator)
        try:
            path_response = await client.post(
                f"{AI_SERVICE_API_URL}/determine-path", 
                json={"query": query}
            )
            # 상태 코드가 200이 아니면 에러 발생시키지 않고 기본값 사용
            if path_response.status_code == 200:
                search_path = path_response.json().get("path", 'INTERNAL')
            else:
                search_path = 'INTERNAL'
            
            logger.info(f"AI determined search path: {search_path}")

        except Exception as e:
            logger.warning(f"AI Path decision failed: {e}. Defaulting to INTERNAL.")
            search_path = 'INTERNAL'

        # B. AI 처리 및 벡터 생성 요청
        # 경로에 따라 엔드포인트 선택
        ai_endpoint = "/process-external" if search_path == 'EXTERNAL' else "/process-internal"
        
        try:
            # 이미지와 텍스트를 함께 전송
            ai_payload = {"query": query, "image_b64": image_b64}
            
            ai_data_response = await client.post(
                f"{AI_SERVICE_API_URL}{ai_endpoint}", 
                json=ai_payload
            )
            ai_data_response.raise_for_status()
            
            ai_data = ai_data_response.json()
            vector: List[float] = ai_data.get("vector", [])
            reason: str = ai_data.get("reason", "AI 검색 결과입니다.")
            
        except Exception as e:
            logger.error(f"AI processing critical error: {e}")
            raise HTTPException(status_code=500, detail=f"AI 서비스 처리 중 오류 발생: {str(e)}")

    # 3. 벡터 유효성 검사
    if not vector or len(vector) != 768:
        logger.error(f"Invalid vector dimension. Expected 768, got {len(vector) if vector else 0}")
        raise HTTPException(status_code=500, detail="AI 벡터 생성 실패 (차원 불일치)")

    # 4. DB Vector 검색 실행 (여기가 핵심)
    try:
        # 🚨 [수정] 이제 crud_product에 search_by_vector가 존재하므로 에러가 나지 않습니다.
        results: List[Product] = await crud_product.search_by_vector(
            db, 
            query_vector=vector, 
            limit=limit
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 벡터 검색 중 오류가 발생했습니다.")

    # 5. 응답 반환
    product_responses = [ProductResponse.model_validate(p) for p in results]
    
    return {
        "status": "SUCCESS",
        "answer": reason,
        "products": product_responses,
        "search_path": search_path
    }

# --------------------------------------------------------------------------
# [기존 코드 유지] 기타 기능 (가격대별, 코디 추천 등)
# --------------------------------------------------------------------------

@router.get("/related-price/{product_id}")
async def get_related_by_price(product_id: int, db: AsyncSession = Depends(get_db)):
    """ 3. 비슷한 가격대의 상품 추천 (구현 예정) """
    return {"message": f"Feature 3: Price-based search for product {product_id} is pending implementation."}

@router.get("/ai-coordination/{product_id}")
async def get_ai_coordination(product_id: int, db: AsyncSession = Depends(get_db)):
    """ 4. AI 코디 추천 (구현 예정) """
    return {"message": f"Feature 4: AI Coordination for product {product_id} is pending implementation."}