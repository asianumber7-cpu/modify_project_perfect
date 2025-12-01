import logging
import csv
import io
import json
import shutil # [필수] 파일 저장을 위해 필요
import os     # [필수] 경로 설정을 위해 필요
import uuid   # [필수] 파일명 중복 방지를 위해 필요
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import httpx 

from src.api.deps import get_db, get_current_user
from src.models.product import Product
from src.schemas.product import ProductResponse, ProductCreate
from src.crud.crud_product import crud_product 
from src.schemas.user import UserResponse as User

logger = logging.getLogger(__name__)
router = APIRouter()

AI_SERVICE_API_URL = "http://ai-service-api:8000/api/v1" 

# --- Pydantic 모델 정의 ---
class LLMQueryBody(BaseModel):
    question: str
    
class CoordinationResponse(BaseModel): 
    answer: str
    products: List[ProductResponse]

# 🚨 Helper: 문자열 내 Null Byte 제거
def sanitize_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "").strip()
    return value

# =========================================================
# 1️⃣ [Mode 1] 이미지 자동 분석 업로드 (AI 분석 + 로컬 저장)
# =========================================================
@router.post("/upload/image-auto", response_model=ProductResponse)
async def upload_product_image_auto(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    이미지를 업로드하면:
    1. 서버 내부 static 폴더에 이미지를 저장하고,
    2. AI가 이미지를 분석하여 상품 정보를 생성한 뒤,
    3. 저장된 이미지 URL과 함께 DB에 등록합니다.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    # -------------------------------------------------------
    # [Step A] AI 서비스로 이미지 전송 (분석 요청)
    # -------------------------------------------------------
    ai_analyzed_data = {}
    
    async with httpx.AsyncClient(timeout=40.0) as client:
        try:
            await file.seek(0) # 파일 포인터 초기화
            files = {"file": (file.filename, file.file, file.content_type)}
            
            response = await client.post(
                f"{AI_SERVICE_API_URL}/analyze-image",
                files=files
            )
            
            if response.status_code != 200:
                logger.error(f"AI Service Error: {response.text}")
                raise HTTPException(status_code=502, detail="AI 서비스 분석 실패")
                
            ai_analyzed_data = response.json()
            
        except httpx.RequestError as e:
            logger.error(f"AI Connection Error: {e}")
            raise HTTPException(status_code=503, detail="AI 서비스 연결 불가")

    # -------------------------------------------------------
    # [Step B] 이미지를 서버 로컬 폴더에 실제로 저장
    # -------------------------------------------------------
    try:
        # 1. 저장할 폴더 경로 (static/images)
        UPLOAD_DIR = "static/images"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 2. 유니크한 파일명 생성 (중복 방지)
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # 3. 파일 저장 
        # (주의: AI 전송 때 파일을 읽었으므로 포인터를 다시 0으로 돌려야 함)
        await file.seek(0) 
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 4. DB에 저장될 접속 가능한 URL 생성
        # (개발 환경: localhost, 실제 배포 시 도메인으로 변경)
        final_image_url = f"http://localhost:8000/static/images/{unique_filename}"
        
    except Exception as e:
        logger.error(f"File Save Error: {e}")
        raise HTTPException(status_code=500, detail="이미지 파일 저장 실패")

    # -------------------------------------------------------
    # [Step C] DB 저장
    # -------------------------------------------------------
    product_in_data = {
        "name": sanitize_string(ai_analyzed_data.get("name", f"Auto Product {file.filename}")),
        "category": sanitize_string(ai_analyzed_data.get("category", "Uncategorized")),
        "description": sanitize_string(ai_analyzed_data.get("description", "")),
        "price": ai_analyzed_data.get("price", 0),
        "stock_quantity": 100,
        "image_url": final_image_url, # 👈 실제 저장된 URL 사용
        "embedding": ai_analyzed_data.get("vector", []),
        "is_active": True
    }

    try:
        new_product = await crud_product.create(db, obj_in=product_in_data)
        return new_product
    except Exception as e:
        logger.error(f"DB Insert Error: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 저장 실패")


# =========================================================
# 2️⃣ [Mode 2] CSV 대량 업로드
# =========================================================
@router.post("/upload/csv")
async def upload_products_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [CSV 전용] CSV 파일을 읽어 대량으로 상품을 등록합니다. (인코딩 자동 감지)
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    # 1. 파일 읽기 및 인코딩 처리
    content = await file.read()
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("cp949")
        except UnicodeDecodeError:
            decoded_content = content.decode("euc-kr", errors="ignore")

    csv_reader = csv.DictReader(io.StringIO(decoded_content))
    
    results = {"success": 0, "failed": 0, "errors": []}

    for row in csv_reader:
        try:
            name = row.get("name") or row.get("상품명")
            if not name: continue 

            category = row.get("category") or row.get("카테고리") or "Uncategorized"
            description = row.get("description") or row.get("설명") or ""
            
            price_raw = row.get("price") or row.get("가격") or "0"
            price = int(str(price_raw).replace(",", "").strip())

            stock_raw = row.get("stock_quantity") or row.get("재고") or "100"
            stock = int(str(stock_raw).replace(",", "").strip())
            
            image_url = row.get("image_url") or row.get("이미지") or "https://placehold.co/400x500?text=No+Image"

            # 임베딩 생성 (AI 서비스 호출)
            vector = []
            text_for_vector = f"{name} {category} {description}"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    res = await client.post(
                        f"{AI_SERVICE_API_URL}/embed-text", 
                        json={"text": text_for_vector}
                    )
                    if res.status_code == 200:
                        vector = res.json().get("vector", [])
                except Exception:
                    pass 

            # DB 저장
            product_in = {
                "name": sanitize_string(name),
                "category": sanitize_string(category),
                "description": sanitize_string(description),
                "price": price,
                "stock_quantity": stock,
                "image_url": image_url,
                "embedding": vector,
                "is_active": True
            }
            
            await crud_product.create(db, obj_in=product_in)
            results["success"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{name}: {str(e)}")

    return results


# =========================================================
# 3️⃣ 기존 일반 API (CRUD, Recommendation, LLM Query)
# =========================================================

@router.post("/", response_model=ProductResponse)
async def create_product(
    *,
    db: AsyncSession = Depends(get_db),
    product_in: ProductCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """단일 상품 직접 생성 (관리자)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    product_data = product_in.model_dump()
    for key, value in product_data.items():
        product_data[key] = sanitize_string(value)

    embedding_vector = []
    text_to_embed = f"상품명: {product_data['name']} | 카테고리: {product_data.get('category', '')} | 설명: {product_data.get('description', '')}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{AI_SERVICE_API_URL}/embed-text",
                json={"text": text_to_embed}
            )
            if response.status_code == 200:
                embedding_vector = response.json().get("vector", [])
    except Exception as e:
        logger.error(f"❌ Failed to generate embedding: {e}")

    if embedding_vector:
        product_data["embedding"] = embedding_vector

    product = await crud_product.create(db, obj_in=product_data)
    return product

@router.get("/{product_id}", response_model=ProductResponse)
async def read_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/{product_id}/llm-query", response_model=Dict[str, str])
async def llm_query_product(
    product_id: int,
    query_body: LLMQueryBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    context = (
        f"상품명: {product.name}, 카테고리: {product.category}, 가격: {product.price}원, "
        f"기존 설명: {product.description}"
    )
    
    prompt = (
        f"사용자 질문: {query_body.question}\n"
        f"다음 상품 정보를 바탕으로 전문가처럼 답변하세요: {context}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            ai_response = await client.post(
                f"{AI_SERVICE_API_URL}/llm-generate-response", 
                json={"prompt": prompt}
            )
            ai_response.raise_for_status()
            ai_data = ai_response.json()
            return {"answer": ai_data.get("answer", "답변을 생성하지 못했습니다.")}
        except Exception as e:
            logger.error(f"LLM Query failed: {e}")
            raise HTTPException(status_code=503, detail="AI 서비스 통신 오류")

@router.get("/ai-coordination/{product_id}", response_model=CoordinationResponse)
async def get_ai_coordination_products(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    if not product or not product.embedding:
        raise HTTPException(status_code=404, detail="상품을 찾거나 벡터를 불러올 수 없습니다.")
    
    coordination_prompt = (
        f"상품명 '{product.name}', 카테고리 '{product.category}'의 코디에 적합한 "
        f"다른 카테고리(예: 상의면 하의, 아우터면 이너)의 상품을 찾기 위한 "
        f"최적의 검색 키워드 5개(스타일, 카테고리 포함)를 쉼표로 구분하여 작성하세요."
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            llm_res = await client.post(
                f"{AI_SERVICE_API_URL}/llm-generate-response", 
                json={"prompt": coordination_prompt}
            )
            llm_res.raise_for_status()
            coordination_keywords = llm_res.json().get("answer", "캐주얼, 기본, 추천").split(',')
            coordination_keywords = [k.strip() for k in coordination_keywords]
        except Exception:
            coordination_keywords = ["기본", "추천", "스타일"]

    embedding_text = f"{product.name} 코디, {', '.join(coordination_keywords)}"
    coordination_vector: List[float]
    try:
        vector_res = await client.post(
            f"{AI_SERVICE_API_URL}/embed-text", 
            json={"text": embedding_text}
        )
        vector_res.raise_for_status()
        coordination_vector = vector_res.json().get("vector", [])
    except Exception as e:
        logger.error(f"Embedding API failed: {e}")
        raise HTTPException(status_code=503, detail="AI 코디 벡터 생성 실패")

    coordination_products = await crud_product.search_by_vector(
        db, 
        query_vector=coordination_vector, 
        limit=5, 
        exclude_category=[product.category]
    )

    coordination_reason = (
        f"이 '{product.name}'와 함께 트렌디한 룩을 완성할 수 있는 "
        f"최적의 코디 상품을 추천해 드립니다. 컨셉: {', '.join(coordination_keywords[:3])}"
    )

    return CoordinationResponse(
        answer=coordination_reason,
        products=[ProductResponse.model_validate(p) for p in coordination_products]
    )

@router.get("/related-price/{product_id}", response_model=CoordinationResponse)
async def get_related_by_price(
    product_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    if not product or not product.embedding:
        raise HTTPException(status_code=404, detail="상품을 찾거나 벡터를 불러올 수 없습니다.")
    
    price_range = product.price * 0.15
    min_p = max(0, int(product.price - price_range))
    max_p = int(product.price + price_range)

    related_products = await crud_product.search_by_vector(
        db, 
        query_vector=product.embedding,
        limit=5,
        min_price=min_p,
        max_price=max_p,
        exclude_id=[product.id]
    )

    reason = (
        f"가격대({min_p:,}원 ~ {max_p:,}원)가 비슷한 상품 중에서, "
        f"'{product.name}'와 스타일이 가장 유사한 상품들을 추천합니다."
    )

    return CoordinationResponse(
        answer=reason,
        products=[ProductResponse.model_validate(p) for p in related_products]
    )

@router.get("/related-color/{product_id}", response_model=CoordinationResponse)
async def get_related_by_color(
    product_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    if not product or not product.embedding:
        raise HTTPException(status_code=404, detail="상품을 찾거나 벡터를 불러올 수 없습니다.")
    
    color_prompt = (
        f"상품 '{product.name}'의 설명('{product.description[:100]}')을 보고, "
        f"가장 지배적인 색상 키워드 1개만 (예: 블랙, 네이비) 답변하시오. [100자 이내]"
    )
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            llm_res = await client.post(
                f"{AI_SERVICE_API_URL}/llm-generate-response", 
                json={"prompt": color_prompt}
            )
            llm_res.raise_for_status()
            target_color = llm_res.json().get("answer", "유사색상")
        except Exception:
            target_color = "유사색상"

    embedding_text = f"{product.name}과 동일한 디자인, {target_color} 색상"

    color_vector: List[float]
    async with httpx.AsyncClient(timeout=10.0) as client:
        vector_res = await client.post(
            f"{AI_SERVICE_API_URL}/embed-text", 
            json={"text": embedding_text}
        )
        vector_res.raise_for_status()
        color_vector = vector_res.json().get("vector", [])
    
    if not color_vector:
        raise HTTPException(status_code=500, detail="색상 벡터 생성 실패")
        
    related_products = await crud_product.search_by_vector(
        db, 
        query_vector=color_vector,
        limit=5,
        exclude_id=[product.id]
    )
    
    reason = (
        f"'{product.name}'의 디자인은 유지하면서, "
        f"'{target_color}' 계열의 비슷한 스타일 상품을 추천합니다."
    )

    return CoordinationResponse(
        answer=reason,
        products=[ProductResponse.model_validate(p) for p in related_products]
    )

@router.get("/related-brand/{product_id}", response_model=CoordinationResponse)
async def get_related_by_brand(
    product_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    if not product or not product.embedding:
        raise HTTPException(status_code=404, detail="상품을 찾거나 벡터를 불러올 수 없습니다.")
    
    style_prompt = (
        f"'{product.name}' 상품의 스타일(예: 미니멀리즘, 스트리트) 키워드 3개만 쉼표로 구분하여 답변하시오."
    )
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            llm_res = await client.post(
                f"{AI_SERVICE_API_URL}/llm-generate-response", 
                json={"prompt": style_prompt}
            )
            llm_res.raise_for_status()
            style_keywords = llm_res.json().get("answer", "유사 스타일").split(',')
        except Exception:
            style_keywords = ["고급스러운", "유사 디자인"]

    embedding_text = f"다른 브랜드, {product.category}의 {', '.join(style_keywords)} 상품"

    brand_vector: List[float]
    async with httpx.AsyncClient(timeout=10.0) as client:
        vector_res = await client.post(
            f"{AI_SERVICE_API_URL}/embed-text", 
            json={"text": embedding_text}
        )
        vector_res.raise_for_status()
        brand_vector = vector_res.json().get("vector", [])
        
    if not brand_vector:
        raise HTTPException(status_code=500, detail="브랜드 벡터 생성 실패")

    related_products = await crud_product.search_by_vector(
        db, 
        query_vector=brand_vector,
        limit=5,
        exclude_id=[product.id] 
    )

    reason = (
        f"'{product.name}'와 비슷한 스타일({', '.join(style_keywords)})이지만, "
        f"다른 브랜드의 유사 상품들을 엄선하여 추천합니다."
    )

    return CoordinationResponse(
        answer=reason,
        products=[ProductResponse.model_validate(p) for p in related_products]
    )