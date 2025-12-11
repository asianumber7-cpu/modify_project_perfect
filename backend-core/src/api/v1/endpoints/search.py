import logging
import base64
import asyncio
import re
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from pydantic import BaseModel, ValidationError 

from src.api import deps
from src.crud.crud_product import crud_product
from src.schemas.product import ProductResponse
from src.config.settings import settings
from src.constants import ProductCategory

logger = logging.getLogger(__name__)
router = APIRouter()

# ------------------------------------------------------------------
# DTO Definitions
# ------------------------------------------------------------------

class ImageAnalysisRequest(BaseModel):
    image_b64: str
    query: str

class ClipSearchRequest(BaseModel):
    image_b64: str
    limit: int = 12
    query: Optional[str] = None  # 원본 검색어 (성별 추출용)
    target: str = "full"  # "full", "upper", "lower"

# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

def detect_gender_intent(query: str) -> Optional[str]:
    """검색어에서 성별 키워드 추출"""
    if not query:
        return None
    q = query.lower()
    if any(x in q for x in ["남자", "남성", "맨", "men", "male", "boy"]):
        return "Male"
    elif any(x in q for x in ["여자", "여성", "우먼", "women", "female", "girl"]):
        return "Female"
    return None

def extract_core_keyword(query: str) -> str:
    """검색어에서 핵심 상품 키워드 추출 (성별/수식어 제거)"""
    if not query:
        return ""
        
    # 제거할 단어들
    remove_words = [
        "남자", "여자", "남성", "여성", "남성용", "여성용",
        "추천", "해줘", "보여줘", "찾아줘", "알려줘",
        "스타일", "패션", "의류", "용"
    ]
    # ✅ [FIX] "옷"은 제거하지 않음 - 검색어로 유의미함
    
    result = query
    for word in remove_words:
        result = result.replace(word, "")
    
    # 조사 제거 (은/는/이/가 등)
    result = re.sub(r'(은|는|이|가|을|를|의|에|로)$', '', result.strip())
    
    return result.strip() if result.strip() else query

def is_celebrity_search(query: str) -> bool:
    """연예인/인물 검색인지 판단"""
    if not query:
        return False
        
    # 패션 관련 키워드와 함께 사용된 경우
    fashion_keywords = ["패션", "스타일", "코디", "룩", "공항", "착장", "의상", "옷"]
    
    # 한글 이름 패턴 (2-4글자)
    korean_name = re.search(r'[가-힣]{2,4}', query)
    
    if korean_name and any(k in query for k in fashion_keywords):
        return True
    
    return False

async def fetch_image_as_base64(url: str) -> Optional[str]:
    """외부 이미지 프록시 다운로드"""
    if not url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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


# ✅ [NEW] Response 매핑 헬퍼 함수
def map_product_to_response(product) -> Optional[ProductResponse]:
    """Product 객체를 ProductResponse로 변환 (similarity 포함)"""
    try:
        p_dict = {
            "id": product.id,
            "name": product.name or "Unnamed Product",
            "description": product.description or "",
            "price": float(product.price) if product.price else 0,
            "stock_quantity": int(product.stock_quantity) if product.stock_quantity else 0,
            "category": product.category or "Etc",
            "image_url": product.image_url or "",
            "gender": product.gender or "Unisex",
            "is_active": product.is_active if product.is_active is not None else True,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "in_stock": (product.stock_quantity or 0) > 0,
            # ✅ [FIX] similarity 필드 추가
            "similarity": getattr(product, 'similarity', None)
        }
        return ProductResponse.model_validate(p_dict)
    except ValidationError as e:
        logger.warning(f"⚠️ Product validation error: {e}")
        return None


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/search-by-clip")
async def search_by_clip_image(
    request: ClipSearchRequest,
    db: AsyncSession = Depends(deps.get_db),
):
    """
    이미지 기반 상품 검색 (CLIP Vector)
    - 후보 이미지 클릭 시 호출
    - 이미지 → CLIP 벡터 → 유사 상품 검색
    - target: "full"(전체), "upper"(상의), "lower"(하의)
    """
    logger.info(f"🖼️ CLIP Image Search Request (limit: {request.limit}, query: {request.query}, target: {request.target})")
    
    # 1. 원본 쿼리에서 성별 추출
    target_gender = None
    if request.query:
        target_gender = detect_gender_intent(request.query)
        logger.info(f"📌 Detected gender from query: {target_gender}")

    target_categories = None
    if request.target == "upper":
        # 상의라고 판단되면 Tops, Outerwear, Dresses 검색
        target_categories = [
            ProductCategory.TOPS.value, 
            ProductCategory.OUTERWEAR.value, 
            ProductCategory.DRESSES.value
        ]
    elif request.target == "lower":
        # 하의라고 판단되면 Bottoms 검색
        target_categories = [ProductCategory.BOTTOMS.value] 
    
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL.rstrip("/")
    
    try:
        # 2. AI 서비스에서 CLIP 벡터 생성 (Fashion CLIP or Standard CLIP)
        async with httpx.AsyncClient(timeout=30.0) as client:
            clip_res = await client.post(
                f"{AI_SERVICE_API_URL}/generate-fashion-clip-vector",
                json={
                    "image_b64": request.image_b64,
                    "target": request.target  # 영역 지정
                }
            )
            
            if clip_res.status_code != 200:
                # Fallback: 기존 CLIP 엔드포인트
                logger.warning("⚠️ Fashion CLIP endpoint failed, falling back to standard CLIP")
                clip_res = await client.post(
                    f"{AI_SERVICE_API_URL}/generate-clip-vector",
                    json={"image_b64": request.image_b64}
                )
            
            if clip_res.status_code != 200:
                raise HTTPException(status_code=500, detail="CLIP 벡터 생성 실패")
            
            clip_data = clip_res.json()
            clip_vector = clip_data.get("vector", [])
            
            if not clip_vector or len(clip_vector) != 512:
                raise HTTPException(status_code=500, detail="유효하지 않은 CLIP 벡터")
        
        logger.info(f"✅ CLIP vector generated: {len(clip_vector)} dims (target: {request.target})")
        
        # 3. CLIP 벡터로 상품 검색 (성별 필터 적용)
        results = await crud_product.search_by_clip_vector(
            db,
            clip_vector=clip_vector,
            limit=request.limit,
            filter_gender=target_gender,
            target=request.target,
            include_category=target_categories
        )
        
        logger.info(f"✅ CLIP search found {len(results)} products (gender filter: {target_gender})")
        
        # 4. Response 구성 (with similarity)
        product_responses = []
        for p in results:
            response = map_product_to_response(p)
            if response:
                product_responses.append(response)
        
        return {
            "status": "SUCCESS",
            "search_type": "CLIP_IMAGE_SIMILARITY",
            "products": product_responses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ CLIP search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-image")
async def analyze_image_proxy(request: ImageAnalysisRequest):
    """개별 이미지 분석 프록시 (후보 이미지 상세 분석)"""
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            target_url = f"{AI_SERVICE_API_URL}/analyze-image-detail"
            # URL 경로 보정
            if "/api/v1" not in AI_SERVICE_API_URL and "/api/v1" not in target_url:
                 # AI Service 구조에 따라 유동적일 수 있음, 여기선 안전하게 기본 경로 사용
                 pass 

            logger.info(f"📤 Calling AI Service: {target_url}")

            response = await client.post(
                target_url,
                json={"image_b64": request.image_b64, "query": request.query}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ AI Service HTTP Error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"❌ Analysis Proxy Failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI Service Error: {str(e)}")


@router.post("/ai-search", response_model=Dict[str, Any])
async def ai_search(
    query: str = Form(..., description="사용자 검색 쿼리"),
    image_file: Optional[UploadFile] = File(None),
    limit: int = Form(12),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    [Upgraded v2] 스마트 하이브리드 검색
    1. 텍스트/이미지 입력 -> AI 서비스로 경로(Internal/External) 판단
    2. EXTERNAL: 외부 이미지/트렌드 분석 -> CLIP 벡터 생성 -> 시각적 유사도 상품 검색
    3. INTERNAL: 핵심 키워드 + BERT/CLIP 벡터 -> 하이브리드 검색
    """
    logger.info(f"🔍 AI Search Request: '{query}' (Image: {image_file is not None})")

    # 1. 의도 및 정보 추출
    target_gender = detect_gender_intent(query)
    core_keyword = extract_core_keyword(query)
    is_celeb_search = is_celebrity_search(query)
    
    logger.info(f"📌 Gender: {target_gender}, Core Keyword: '{core_keyword}', Celebrity: {is_celeb_search}")

    # 2. 업로드 이미지 처리
    image_b64: Optional[str] = None
    if image_file:
        try:
            content = await image_file.read()
            image_b64 = base64.b64encode(content).decode("utf-8")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")

    # 3. AI Service 호출 (경로 판단 및 벡터 생성)
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL.rstrip("/")
    
    search_strategy = "SMART_HYBRID"
    search_path = "INTERNAL"
    ai_summary = "검색 결과입니다."
    ref_image_url = None
    candidates = []
    
    bert_vec: Optional[List[float]] = None
    clip_vec: Optional[List[float]] = None
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 3-1. 경로 결정 API 호출
                path_res = await client.post(
                    f"{AI_SERVICE_API_URL}/determine-path",
                    json={"query": query}
                )
                
                search_path = "INTERNAL"
                if path_res.status_code == 200:
                    search_path = path_res.json().get("path", "INTERNAL")
                
                logger.info(f"🛤️ Search Path Decision: {search_path}")
                
                # 3-2. 경로에 따른 상세 처리 호출
                endpoint = "/process-external" if search_path == 'EXTERNAL' else "/process-internal"
                
                # URL 결합 시 중복 슬래시 방지
                target_ai_url = f"{AI_SERVICE_API_URL}{endpoint}"
                
                payload = {"query": query, "image_b64": image_b64}
                ai_res = await client.post(target_ai_url, json=payload)
                ai_res.raise_for_status()
                
                data = ai_res.json()
                
                # 벡터 추출
                if "vectors" in data:
                    bert_vec = data["vectors"].get("bert")
                    clip_vec = data["vectors"].get("clip")
                    logger.info(f"📊 Vectors received - BERT: {len(bert_vec) if bert_vec else 0}dim, CLIP: {len(clip_vec) if clip_vec else 0}dim")
                elif "vector" in data:
                    bert_vec = data["vector"]
                
                # AI 분석 결과 추출
                if "ai_analysis" in data and data["ai_analysis"]:
                    analysis = data["ai_analysis"]
                    ai_summary = analysis.get("summary") or ai_summary
                    ref_image_url = analysis.get("reference_image")
                    candidates = analysis.get("candidates", [])
                else:
                    ai_summary = data.get("description") or data.get("reason") or ai_summary
                    ref_image_url = data.get("ref_image")
                
                search_strategy = data.get("strategy", search_path).upper()
                
                # 외부 이미지 URL이면 프록시 처리 (CORS 방지)
                if ref_image_url and ref_image_url.startswith("http"):
                    logger.info(f"🔄 Proxying reference image...")
                    proxy_image = await fetch_image_as_base64(ref_image_url)
                    if proxy_image:
                        ref_image_url = proxy_image
                
                break  # 성공 시 재시도 루프 탈출

        except Exception as e:
            logger.warning(f"⚠️ AI Service Retry ({attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                search_strategy = "KEYWORD_FALLBACK"
                logger.error(f"❌ AI Service failed after {max_retries} retries")
            await asyncio.sleep(1)

    # 4. 🌟 검색 실행 - DB 조회
    results = []
    gender_filtered = True  # 성별 필터 적용 여부 추적
    
    try:
        # Case A: EXTERNAL 경로이면서 CLIP 벡터가 있는 경우 (핵심 기능!)
        if search_path == "EXTERNAL" and clip_vec and len(clip_vec) == 512:
            logger.info(f"🖼️ Using CLIP image vector search (512-dim)")
            
            # CLIP 이미지 벡터로 시각적 유사도 검색
            results = await crud_product.search_by_clip_vector(
                db,
                clip_vector=clip_vec,
                limit=limit,
                filter_gender=target_gender
            )
            
            if results:
                search_strategy = "CLIP_VISUAL_SEARCH"
                logger.info(f"✅ CLIP search found {len(results)} products")
            else:
                # CLIP 검색 결과 없으면 BERT로 Fallback
                logger.info(f"⚠️ CLIP search empty, falling back to BERT")
                if bert_vec and len(bert_vec) == 768:
                    results = await crud_product.search_hybrid(
                        db,
                        bert_vector=bert_vec,
                        limit=limit,
                        filter_gender=target_gender
                    )
                    search_strategy = "BERT_FALLBACK"
        
        # Case B: INTERNAL 경로 또는 벡터 검색 실패 시 -> 스마트 하이브리드 (키워드 + 벡터)
        if not results:
            results = await crud_product.search_smart_hybrid(
                db,
                query=core_keyword,  # 핵심 키워드 우선
                bert_vector=bert_vec,
                clip_vector=clip_vec,
                limit=limit,
                filter_gender=target_gender
            )
            
            # ✅ [FIX] 결과 없으면 성별 필터를 완화하되 전체 쿼리로 재시도
            # 하지만 필터 완화 사실을 추적
            if not results:
                logger.info(f"⚠️ No results with gender filter '{target_gender}', trying relaxed search")
                results = await crud_product.search_smart_hybrid(
                    db,
                    query=query,
                    bert_vector=bert_vec,
                    clip_vector=clip_vec,
                    limit=limit,
                    filter_gender=None  # 성별 필터 해제
                )
                if results:
                    search_strategy = "RELAXED_SEARCH"
                    gender_filtered = False
                    logger.info(f"⚠️ Relaxed search found {len(results)} products (gender filter removed)")
        
        # Case C: 최후의 수단 (최신 상품)
        if not results:
            results = await crud_product.get_multi(db, limit=limit)
            search_strategy = "FALLBACK_LATEST"
            gender_filtered = False

    except Exception as e:
        logger.error(f"❌ DB Search Error: {e}")
        # DB 에러가 나도 앱이 죽지 않도록 빈 리스트 반환 혹은 에러 처리
        raise HTTPException(status_code=500, detail="Database Search Failed")

    # 5. ✅ [FIX] Response 매핑 (similarity 포함)
    product_responses = []
    for p in results:
        response = map_product_to_response(p)
        if response:
            product_responses.append(response)

    logger.info(f"✅ Search Complete: {len(product_responses)} products found (Strategy: {search_strategy})")

    return {
        "status": "SUCCESS",
        "search_path": search_strategy,
        "gender_filter_applied": gender_filtered,  # ✅ [NEW] 성별 필터 적용 여부
        "detected_gender": target_gender,  # ✅ [NEW] 감지된 성별
        "ai_analysis": {
            "summary": ai_summary,
            "reference_image": ref_image_url,
            "candidates": candidates
        },
        "products": product_responses
    }