import logging
import base64
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
# [중요] BaseModel Import 추가 (오류 해결)
from pydantic import BaseModel, ValidationError 

from src.api import deps
from src.crud.crud_product import crud_product
from src.schemas.product import ProductResponse
from src.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# [NEW] 이미지 상세 분석 요청을 위한 데이터 모델 정의
class ImageAnalysisRequest(BaseModel):
    image_b64: str
    query: str

def detect_gender_intent(query: str) -> Optional[str]:
    """검색어에서 성별 키워드 추출"""
    q = query.lower()
    if any(x in q for x in ["남자", "남성", "맨", "men", "male", "boy"]):
        return "Male"
    elif any(x in q for x in ["여자", "여성", "우먼", "women", "female", "girl"]):
        return "Female"
    return None

# [복원] 외부 이미지 프록시 다운로드 (CORS/403 방지)
async def fetch_image_as_base64(url: str) -> Optional[str]:
    if not url: return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.google.com/" 
        }
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                b64_data = base64.b64encode(response.content).decode('utf-8')
                content_type = response.headers.get("content-type", "image/jpeg")
                return f"data:{content_type};base64,{b64_data}"
    except Exception as e:
        logger.warning(f"⚠️ Failed to proxy image ({url}): {e}")
    return None

# [NEW] 개별 이미지 분석 프록시 엔드포인트
@router.post("/analyze-image")
async def analyze_image_proxy(request: ImageAnalysisRequest):
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL.rstrip("/") # 끝에 슬래시 제거
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # AI Service 경로를 명확하게 지정
            target_url = f"{AI_SERVICE_API_URL}/analyze-image"
            
            # 만약 settings에 /api/v1이 없다면 추가해야 함. 
            # 보통 AI_SERVICE_API_URL이 "http://ai-service-api:8000/api/v1" 이라면 위처럼, 
            # "http://ai-service-api:8000" 이라면 아래처럼 수정:
            if "/api/v1" not in AI_SERVICE_API_URL:
                target_url = f"{AI_SERVICE_API_URL}/api/v1/analyze-image"

            response = await client.post(
                target_url,
                json={"image_b64": request.image_b64, "query": request.query}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"❌ Analysis Proxy Failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI Service Error: {str(e)}")

@router.post("/ai-search", response_model=Dict[str, Any])
async def ai_search(
    query: str = Form(..., description="사용자 검색 쿼리"),
    image_file: Optional[UploadFile] = File(None),
    limit: int = Form(10),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    [Hybrid] 통합 AI 기반 상품 검색 (Visual RAG + Text Context)
    """
    logger.info(f"🔍 AI Search Request: '{query}' (Image: {image_file is not None})")

    # 1. 성별 의도 파악
    target_gender = detect_gender_intent(query)
    
    # 2. 이미지 처리
    image_b64: Optional[str] = None
    if image_file:
        try:
            content = await image_file.read()
            image_b64 = base64.b64encode(content).decode("utf-8")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")

    # 3. AI Service 호출
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    
    search_strategy = "INTERNAL"
    ai_summary = "검색 결과입니다."
    ref_image_url = None
    candidates = [] 
    
    bert_vec: Optional[List[float]] = None
    clip_vec: Optional[List[float]] = None
    
    # [복원] 재시도 로직 (안정성 확보)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 3-1. 경로 결정
                path_res = await client.post(
                    f"{AI_SERVICE_API_URL}/determine-path", 
                    json={"query": query}
                )
                path = path_res.json().get("path", "INTERNAL") if path_res.status_code == 200 else "INTERNAL"
                
                # 3-2. 데이터 처리 요청
                endpoint = "/process-external" if path == 'EXTERNAL' else "/process-internal"
                payload = {"query": query, "image_b64": image_b64}
                
                ai_res = await client.post(
                    f"{AI_SERVICE_API_URL}{endpoint}", 
                    json=payload
                )
                ai_res.raise_for_status()
                
                data = ai_res.json()
                
                # 벡터 추출 (구조 안전하게 파싱)
                if "vectors" in data:
                    vectors = data["vectors"]
                    bert_vec = vectors.get("bert")
                    clip_vec = vectors.get("clip")
                elif "vector" in data:
                    bert_vec = data["vector"]
                
                # 분석 데이터 추출
                if "ai_analysis" in data and data["ai_analysis"]:
                    analysis = data["ai_analysis"]
                    ai_summary = analysis.get("summary") or ai_summary
                    ref_image_url = analysis.get("reference_image")
                    candidates = analysis.get("candidates", [])
                else:
                    ai_summary = data.get("description") or data.get("reason") or ai_summary
                    ref_image_url = data.get("ref_image")
                
                search_strategy = data.get("strategy", path).upper()
                
                # [복원] 이미지 URL 프록시 처리 (필수)
                if ref_image_url and ref_image_url.startswith("http"):
                    logger.info(f"🔄 Proxying image: {ref_image_url}")
                    proxy_image = await fetch_image_as_base64(ref_image_url)
                    if proxy_image:
                        ref_image_url = proxy_image
                
                break # 성공 시 탈출

        except Exception as e:
            logger.warning(f"⚠️ AI Service Retry ({attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                search_strategy = "INTERNAL"
            await asyncio.sleep(1)

    # 4. Hybrid Search 실행
    try:
        results = await crud_product.search_hybrid(
            db, 
            bert_vector=bert_vec, 
            clip_vector=clip_vec,
            limit=limit, 
            filter_gender=target_gender
        )
        
        # 결과가 없으면 키워드 검색 Fallback
        if not results and query:
            results = await crud_product.search_keyword(
                db, 
                query=query, 
                limit=limit, 
                filter_gender=target_gender
            )
            search_strategy = "KEYWORD_FALLBACK" 

    except Exception as e:
        logger.error(f"❌ DB Search Error: {e}")
        raise HTTPException(status_code=500, detail="Database Search Failed")

    # 5. Response 구성
    product_responses = []
    for p in results:
        try:
            p_dict = {
                "id": p.id,
                "name": p.name or "Unnamed Product",
                "description": p.description or "",
                "price": float(p.price) if p.price else 0,
                "stock_quantity": int(p.stock_quantity) if p.stock_quantity else 0,
                "category": p.category or "Etc",
                "image_url": p.image_url or "",
                "gender": p.gender or "Unisex",
                "is_active": p.is_active if p.is_active is not None else True,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "in_stock": (p.stock_quantity or 0) > 0
            }
            validated_product = ProductResponse.model_validate(p_dict)
            product_responses.append(validated_product)
        except ValidationError: continue

    return {
        "status": "SUCCESS",
        "search_path": search_strategy, 
        "ai_analysis": {
            "summary": ai_summary,
            "reference_image": ref_image_url,
            "candidates": candidates
        },
        "products": product_responses
    }