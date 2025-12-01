import os
import httpx
import logging
from typing import List
from celery import shared_task

# 내부 모듈 임포트
from src.worker import celery_app
from src.core.model_engine import model_engine # LLM/Embedding 모델
from src.core.config import settings

logger = logging.getLogger(__name__)

# Backend Core API URL (상품 업데이트용)
# Docker Compose 서비스명 사용
BACKEND_CORE_API_URL = f"http://backend-core:8000/api/v1" 

# --------------------------------------------------------------------------
# Celery Shared Task: 상품 상세 설명 및 벡터 생성
# --------------------------------------------------------------------------
@celery_app.task(name="process_product_ai_data")
def process_product_ai_data(product_id: int, name: str, category: str, price: float):
    """
    관리자 상품 업로드 후, 비동기로 LLM 호출 및 벡터를 생성하여 DB에 업데이트합니다.
    """
    logger.info(f"💡 Starting AI processing for Product ID: {product_id} - {name}")
    
    # 1. LLM으로 상세 설명 생성
    coordination_prompt = (
        f"당신은 전문 쇼핑몰 카피라이터입니다. 상품명: {name}, 카테고리: {category}, 가격: {price}원을 바탕으로 "
        f"고객의 구매를 유도하는 매력적인 상품 상세 설명을 한국어로 4문장으로 작성해주세요."
    )
    
    # Celery task는 동기 컨텍스트에서 실행되므로, model_engine의 동기 호출 메서드를 사용합니다.
    try:
        # LLM 호출 (동기)
        llm_answer = model_engine.text_llm.invoke(coordination_prompt).content
        
    except Exception as e:
        logger.error(f"LLM generation failed for product {product_id}: {e}")
        llm_answer = f"[AI 오류] 상세 설명 생성 실패: {name}. Error: {str(e)}"

    # 2. 벡터 생성 (768차원)
    embedding_text = f"상품명: {name} | 카테고리: {category} | 설명: {llm_answer}"
    try:
        # Embedding 호출 (동기)
        embedding_vector = model_engine.generate_embedding(embedding_text)
    except Exception as e:
        logger.error(f"Embedding generation failed for product {product_id}: {e}")
        embedding_vector = [0.0] * settings.EMBEDDING_DIMENSION # 768차원 0 벡터 (실패 시)

    # 3. Backend Core로 업데이트 요청 (HTTP PATCH)
    update_data = {
        "description": llm_answer,
        "embedding": embedding_vector,
        "is_processed": True # 처리 완료 플래그 (Product 모델에 있어야 함)
    }
    
    # Backend Core의 /products/{product_id} 엔드포인트를 호출
    try:
        # NOTE: 이 API는 관리자 권한을 필요로 할 수 있습니다. 
        # 실제 환경에서는 관리자 토큰을 환경 변수 등에서 가져와 Authorization 헤더에 주입해야 합니다.
        response = httpx.patch(
            f"{BACKEND_CORE_API_URL}/products/{product_id}", 
            json=update_data,
            # headers={'Authorization': 'Bearer ADMIN_TOKEN_HERE'} 
        )
        response.raise_for_status()
        logger.info(f"✅ Product ID {product_id} successfully updated in DB.")

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ DB update failed (HTTP Error {e.response.status_code}) for product {product_id}. Response: {e.response.text}")
    except Exception as e:
        logger.error(f"❌ DB update failed (Network Error) for product {product_id}: {e}")