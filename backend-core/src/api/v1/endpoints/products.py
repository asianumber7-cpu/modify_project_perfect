import logging
import csv
import io
import os
import uuid
import base64
from typing import Any, Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import httpx

from src.api import deps
from src.crud.crud_product import crud_product
from src.config.settings import settings
from src.schemas.user import UserResponse as User
from src.schemas.product import (
    ProductResponse, 
    ProductCreate, 
    ProductUpdate,
    CoordinationResponse, 
    LLMQueryBody
)
from src.models.product import Product

logger = logging.getLogger(__name__)
router = APIRouter()

# =========================================================
# 📁 이미지 저장 경로 설정
# =========================================================
STATIC_DIR = Path("/app/static")
IMAGES_DIR = STATIC_DIR / "images"


def sanitize_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "").strip()
    return value


async def _heal_product_embedding(db: AsyncSession, product: Any) -> Any:
    """상품 데이터(임베딩, 설명) 누락 시 AI 서비스로 복구"""
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    
    is_broken = (
        product.embedding is None or 
        (isinstance(product.embedding, list) and len(product.embedding) == 0) or
        product.description == "AI 분석 실패" or 
        not product.description
    )
    
    if not is_broken:
        return product 

    logger.warning(f"🚑 [Self-Healing] Product ID {product.id} data missing...")

    new_description = product.description
    if not product.description or product.description == "AI 분석 실패":
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                prompt = f"상품명: {product.name}, 카테고리: {product.category}. 매력적인 쇼핑몰 상세 설명을 5문장 작성해줘."
                res = await client.post(f"{AI_SERVICE_API_URL}/llm-generate-response", json={"prompt": prompt})
                if res.status_code == 200:
                    new_description = res.json().get("answer", product.name)
        except Exception as e:
            logger.error(f"Heal Description Failed: {e}")

    new_vector = product.embedding
    try:
        text_to_embed = f"{product.name} {product.category} {new_description}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(f"{AI_SERVICE_API_URL}/embed-text", json={"text": text_to_embed})
            if res.status_code == 200:
                new_vector = res.json().get("vector", [])
    except Exception as e:
        logger.error(f"Heal Embedding Failed: {e}")

    if new_vector is not None and len(new_vector) > 0:
        update_data = {"embedding": new_vector}
        if new_description != product.description:
            update_data["description"] = new_description
        product = await crud_product.update(db, db_obj=product, obj_in=update_data)
        logger.info(f"✅ Product {product.id} healed.")
    
    return product


# =========================================================
# [관리자] 상품 목록 조회 (페이징, 검색, 필터)
# =========================================================
@router.get("/", response_model=Dict[str, Any])
async def get_products_list(
    db: AsyncSession = Depends(deps.get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """상품 목록 조회 (관리자용 페이징)"""
    conditions = [
        Product.is_active == True,
        Product.deleted_at.is_(None)
    ]
    
    if search:
        conditions.append(Product.name.ilike(f"%{search}%"))
    
    if category and category not in ["all", "전체 카테고리"]:
        conditions.append(Product.category == category)
    
    if gender and gender != "all":
        conditions.append(Product.gender == gender)
    
    count_stmt = select(func.count(Product.id)).where(*conditions)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    stats_conditions = [Product.is_active == True, Product.deleted_at.is_(None)]
    
    selling_stmt = select(func.count(Product.id)).where(*stats_conditions, Product.stock_quantity > 0)
    selling_result = await db.execute(selling_stmt)
    selling_count = selling_result.scalar() or 0
    
    soldout_stmt = select(func.count(Product.id)).where(*stats_conditions, Product.stock_quantity == 0)
    soldout_result = await db.execute(soldout_stmt)
    soldout_count = soldout_result.scalar() or 0
    
    avg_stmt = select(func.avg(Product.price)).where(*stats_conditions)
    avg_result = await db.execute(avg_stmt)
    avg_price = int(avg_result.scalar() or 0)
    
    offset = (page - 1) * limit
    stmt = select(Product).where(*conditions).order_by(Product.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    return {
        "products": [ProductResponse.model_validate(p) for p in products],
        "total": total,
        "page": page,
        "limit": limit,
        "stats": {
            "total": total,
            "selling": selling_count,
            "soldout": soldout_count,
            "avg_price": avg_price
        }
    }


# =========================================================
# [관리자] 상품 수정
# =========================================================
@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    update_data = product_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        update_data[key] = sanitize_string(value)
    
    updated_product = await crud_product.update(db, db_obj=product, obj_in=update_data)
    logger.info(f"✅ Product {product_id} updated by {current_user.email}")
    
    return updated_product


# =========================================================
# [관리자] 상품 삭제 (하드 삭제 + 이미지 파일 삭제)
# =========================================================
@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    stmt = select(Product).where(Product.id == product_id)
    result = await db.execute(stmt)
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    image_deleted = False
    if product.image_url:
        try:
            image_filename = product.image_url.split("/")[-1]
            image_path = IMAGES_DIR / image_filename
            
            if image_path.exists():
                os.remove(image_path)
                image_deleted = True
                logger.info(f"🗑️ Image deleted: {image_path}")
            else:
                logger.warning(f"⚠️ Image not found: {image_path}")
        except Exception as e:
            logger.error(f"❌ Failed to delete image: {e}")
    
    deleted = await crud_product.hard_delete(db, product_id=product_id)
    
    if not deleted:
        raise HTTPException(status_code=500, detail="삭제에 실패했습니다.")
    
    logger.info(f"🗑️ Product {product_id} permanently deleted by {current_user.email}")
    
    return {
        "success": True,
        "message": "상품이 완전히 삭제되었습니다.",
        "product_id": product_id,
        "image_deleted": image_deleted
    }


# =========================================================
# 🆕 [관리자] 여러 상품 일괄 삭제 (업로드 취소용)
# =========================================================
from pydantic import BaseModel

class BulkDeleteRequest(BaseModel):
    product_ids: List[int]

@router.post("/bulk-delete")
async def bulk_delete_products(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """여러 상품 일괄 삭제 (업로드 취소 시 사용)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    deleted_count = 0
    image_deleted_count = 0
    errors = []
    
    for product_id in request.product_ids:
        try:
            stmt = select(Product).where(Product.id == product_id)
            result = await db.execute(stmt)
            product = result.scalars().first()
            
            if not product:
                errors.append(f"ID {product_id}: 상품 없음")
                continue
            
            if product.image_url:
                try:
                    image_filename = product.image_url.split("/")[-1]
                    image_path = IMAGES_DIR / image_filename
                    
                    if image_path.exists():
                        os.remove(image_path)
                        image_deleted_count += 1
                        logger.info(f"🗑️ Image deleted: {image_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to delete image for product {product_id}: {e}")
            
            await crud_product.hard_delete(db, product_id=product_id)
            deleted_count += 1
            
        except Exception as e:
            errors.append(f"ID {product_id}: {str(e)}")
    
    logger.info(f"🗑️ Bulk delete: {deleted_count} products, {image_deleted_count} images by {current_user.email}")
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "image_deleted_count": image_deleted_count,
        "errors": errors
    }


# =========================================================
# 상품 조회
# =========================================================
@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# =========================================================
# ✅ FIX: 이미지 업로드 (AI 서비스 호출 방식 수정)
# =========================================================
@router.post("/upload/image-auto", response_model=ProductResponse)
async def upload_product_image_auto(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """이미지 업로드 후 AI 분석으로 상품 자동 등록"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    file_ext = file.filename.split(".")[-1] if file.filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = IMAGES_DIR / unique_filename
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    image_url = f"/static/images/{unique_filename}"
    logger.info(f"📁 Image saved: {file_path}")

    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    image_base64 = base64.b64encode(contents).decode("utf-8")
    
    product_name = file.filename or "AI 분석 상품"
    category = "Tops"
    gender = "Unisex"
    description = "AI 분석 중..."
    price = 50000
    
    bert_vector = []
    clip_vector = []
    clip_upper_vector = []
    clip_lower_vector = []

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        # =========================================================
        # 1. 이미지 분석 - ✅ FIX: multipart/form-data로 전송
        # =========================================================
        try:
            files = {"file": (file.filename, contents, f"image/{file_ext}")}
            analyze_res = await http_client.post(
                f"{AI_SERVICE_API_URL}/analyze-image",
                files=files
            )
            
            if analyze_res.status_code == 200:
                data = analyze_res.json()
                product_name = data.get("name", product_name)
                category = data.get("category", category)
                gender = data.get("gender", gender)
                description = data.get("description", description)
                price = data.get("price", price)
                
                bert_vector = data.get("vector", [])
                clip_vector = data.get("vector_clip", [])
                clip_upper_vector = data.get("vector_clip_upper", [])
                clip_lower_vector = data.get("vector_clip_lower", [])
                
                logger.info(f"✅ AI Analysis success: {product_name}")
            else:
                logger.warning(f"⚠️ AI Analysis failed: {analyze_res.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Image analyze failed: {e}")

        # =========================================================
        # 2. BERT 벡터 (필요시)
        # =========================================================
        if not bert_vector or len(bert_vector) == 0:
            try:
                text_to_embed = f"{product_name} {category} {description}"
                embed_res = await http_client.post(
                    f"{AI_SERVICE_API_URL}/embed-text",
                    json={"text": text_to_embed}
                )
                if embed_res.status_code == 200:
                    bert_vector = embed_res.json().get("vector", [])
            except Exception as e:
                logger.error(f"❌ Text embedding failed: {e}")

        # =========================================================
        # 3. CLIP 벡터 - ✅ FIX: /generate-fashion-clip-vector 사용
        # =========================================================
        if not clip_vector or len(clip_vector) == 0:
            try:
                clip_res = await http_client.post(
                    f"{AI_SERVICE_API_URL}/generate-fashion-clip-vector",
                    json={"image_b64": image_base64, "target": "full"}
                )
                if clip_res.status_code == 200:
                    clip_vector = clip_res.json().get("vector", [])
            except Exception as e:
                logger.error(f"❌ CLIP full embedding failed: {e}")
        
        if not clip_upper_vector or len(clip_upper_vector) == 0:
            try:
                clip_upper_res = await http_client.post(
                    f"{AI_SERVICE_API_URL}/generate-fashion-clip-vector",
                    json={"image_b64": image_base64, "target": "upper"}
                )
                if clip_upper_res.status_code == 200:
                    clip_upper_vector = clip_upper_res.json().get("vector", [])
            except Exception as e:
                logger.error(f"❌ CLIP upper embedding failed: {e}")
        
        if not clip_lower_vector or len(clip_lower_vector) == 0:
            try:
                clip_lower_res = await http_client.post(
                    f"{AI_SERVICE_API_URL}/generate-fashion-clip-vector",
                    json={"image_b64": image_base64, "target": "lower"}
                )
                if clip_lower_res.status_code == 200:
                    clip_lower_vector = clip_lower_res.json().get("vector", [])
            except Exception as e:
                logger.error(f"❌ CLIP lower embedding failed: {e}")

    product_data = {
        "name": sanitize_string(product_name),
        "description": sanitize_string(description),
        "price": price,
        "stock_quantity": 100,
        "category": category,
        "gender": gender,
        "image_url": image_url,
        "embedding": bert_vector if bert_vector else None,
        "embedding_clip": clip_vector if clip_vector else None,
        "embedding_clip_upper": clip_upper_vector if clip_upper_vector else None,
        "embedding_clip_lower": clip_lower_vector if clip_lower_vector else None,
    }

    new_product = await crud_product.create(db, obj_in=product_data)
    logger.info(f"✅ Product created: ID={new_product.id}, Name={product_name}")
    
    return new_product


@router.post("/upload/csv")
async def upload_products_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, Any]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    contents = await file.read()
    decoded = contents.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    
    success_count = 0
    fail_count = 0
    errors = []

    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL

    for idx, row in enumerate(reader, start=1):
        try:
            name = sanitize_string(row.get("name", ""))
            category = sanitize_string(row.get("category", "Tops"))
            price_str = row.get("price", "0")
            price = int(float(price_str)) if price_str else 0
            stock = int(row.get("stock_quantity", 100))
            description = sanitize_string(row.get("description", ""))
            gender = sanitize_string(row.get("gender", "Unisex"))
            image_url = sanitize_string(row.get("image_url", ""))

            if not name:
                errors.append(f"Row {idx}: name 필수")
                fail_count += 1
                continue

            bert_vector = []
            try:
                text_to_embed = f"{name} {category} {description}"
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    res = await http_client.post(f"{AI_SERVICE_API_URL}/embed-text", json={"text": text_to_embed})
                    if res.status_code == 200:
                        bert_vector = res.json().get("vector", [])
            except:
                pass

            product_data = {
                "name": name,
                "category": category,
                "price": price,
                "stock_quantity": stock,
                "description": description or f"{name} 상품입니다.",
                "gender": gender,
                "image_url": image_url,
                "embedding": bert_vector if bert_vector else None,
            }

            await crud_product.create(db, obj_in=product_data)
            success_count += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            fail_count += 1

    return {
        "success": success_count,
        "failed": fail_count,
        "errors": errors[:10]
    }


@router.post("/{product_id}/llm-query")
async def llm_query_product(
    product_id: int,
    query_body: LLMQueryBody,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Dict[str, str]:
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product = await _heal_product_embedding(db, product)

    context = f"상품명: {product.name}, 카테고리: {product.category}, 가격: {product.price}원, 설명: {product.description}, 성별: {product.gender}"
    prompt = f"사용자 질문: {query_body.question}\n다음 상품 정보를 바탕으로 친절하게 답변하세요.\n정보: {context}"
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            ai_response = await http_client.post(f"{AI_SERVICE_API_URL}/llm-generate-response", json={"prompt": prompt})
            ai_response.raise_for_status()
            return {"answer": ai_response.json().get("answer", "답변을 생성하지 못했습니다.")}
        except Exception as e:
            logger.error(f"LLM Query failed: {e}")
            raise HTTPException(status_code=503, detail="AI 서비스 통신 오류")


@router.get("/ai-coordination/{product_id}", response_model=CoordinationResponse)
async def get_ai_coordination_products(
    product_id: int, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_user),
) -> CoordinationResponse:
    
    product = await crud_product.get(db, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product = await _heal_product_embedding(db, product)
    
    has_embedding = product.embedding is not None and len(product.embedding) > 0
    if not has_embedding:
        raise HTTPException(status_code=503, detail="AI Service unavailable")
    
    coordination_prompt = (
        f"상품명 '{product.name}', 카테고리 '{product.category}'와 함께 코디하면 예쁜 "
        f"다른 아이템 키워드 3개만 한국어 단어로 쉼표(,)로 구분해서 출력해.\n"
        f"절대 설명이나 문장을 쓰지 마. 오직 단어만 출력해.\n"
        f"예시: 블라우스, 가디건, 로퍼"
    )
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    coordination_keywords = ["추천", "베이직", "데일리"]

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            llm_res = await http_client.post(f"{AI_SERVICE_API_URL}/llm-generate-response", json={"prompt": coordination_prompt})
            if llm_res.status_code == 200:
                answer_text = llm_res.json().get("answer", "")
                extracted = [k.strip() for k in answer_text.split(',') if k.strip()]
                if extracted:
                    coordination_keywords = extracted
        except Exception as e:
            logger.error(f"LLM failed: {e}")

    embedding_text = f"{product.name} 코디 {' '.join(coordination_keywords)}"
    coordination_vector = list(product.embedding) if product.embedding is not None else []
    
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            vector_res = await http_client.post(f"{AI_SERVICE_API_URL}/embed-text", json={"text": embedding_text})
            if vector_res.status_code == 200:
                coordination_vector = vector_res.json().get("vector", coordination_vector)
        except:
            pass

    coordination_products = await crud_product.search_by_vector(
        db, query_vector=coordination_vector, limit=5, exclude_category=[product.category]
    )

    return CoordinationResponse(
        answer=f"'{product.name}'와 완벽한 매치 아이템들입니다.\nAI 추천: #{', #'.join(coordination_keywords[:3])}",
        products=[ProductResponse.model_validate(p) for p in coordination_products]
    )


@router.get("/related-price/{product_id}", response_model=CoordinationResponse)
async def get_related_by_price(
    product_id: int, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    product = await _heal_product_embedding(db, product) 
    
    if not product or product.embedding is None:
        raise HTTPException(status_code=404, detail="AI Analysis Required")
    
    price_range = product.price * 0.15
    min_p = max(0, int(product.price - price_range))
    max_p = int(product.price + price_range)

    related = await crud_product.search_by_vector(
        db, query_vector=product.embedding, limit=5, min_price=min_p, max_price=max_p, exclude_id=[product.id]
    )

    return CoordinationResponse(
        answer=f"가격대({min_p:,}원 ~ {max_p:,}원)가 비슷한 상품 중 '{product.name}'와 스타일이 유사한 상품들입니다.",
        products=[ProductResponse.model_validate(p) for p in related]
    )


@router.get("/related-color/{product_id}", response_model=CoordinationResponse)
async def get_related_by_color(
    product_id: int, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    product = await _heal_product_embedding(db, product)
    
    if not product or product.embedding is None:
        raise HTTPException(status_code=404, detail="AI Analysis Required")
    
    color_prompt = f"상품 '{product.name}'의 가장 지배적인 색상 키워드 1개만 답변하시오."
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    target_color = "유사색상"
    
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        try:
            llm_res = await http_client.post(f"{AI_SERVICE_API_URL}/llm-generate-response", json={"prompt": color_prompt})
            if llm_res.status_code == 200:
                target_color = llm_res.json().get("answer", "유사색상")
        except:
            pass

    embedding_text = f"{product.name} 디자인 {target_color} 색상"
    color_vector = product.embedding 
    
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        try:
            vector_res = await http_client.post(f"{AI_SERVICE_API_URL}/embed-text", json={"text": embedding_text})
            if vector_res.status_code == 200:
                color_vector = vector_res.json().get("vector", [])
        except:
            pass
    
    related = await crud_product.search_by_vector(db, query_vector=color_vector, limit=5, exclude_id=[product.id])
    
    return CoordinationResponse(
        answer=f"'{product.name}'의 디자인을 유지하면서 '{target_color}' 계열 상품을 추천합니다.",
        products=[ProductResponse.model_validate(p) for p in related]
    )


@router.get("/related-brand/{product_id}", response_model=CoordinationResponse)
async def get_related_by_brand(
    product_id: int, 
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> CoordinationResponse:
    product = await crud_product.get(db, product_id=product_id)
    product = await _heal_product_embedding(db, product)
    
    if not product or product.embedding is None:
        raise HTTPException(status_code=404, detail="AI Analysis Required")
    
    style_prompt = f"'{product.name}' 상품의 스타일 키워드 3개만 쉼표로 구분하여 답변하시오."
    AI_SERVICE_API_URL = settings.AI_SERVICE_API_URL
    style_keywords = ["유사 스타일"]
    
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        try:
            llm_res = await http_client.post(f"{AI_SERVICE_API_URL}/llm-generate-response", json={"prompt": style_prompt})
            if llm_res.status_code == 200:
                text = llm_res.json().get("answer", "")
                style_keywords = [k.strip() for k in text.split(',') if k.strip()]
        except:
            pass

    embedding_text = f"다른 브랜드 {product.category} {', '.join(style_keywords)}"
    brand_vector = product.embedding 
    
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        try:
            vector_res = await http_client.post(f"{AI_SERVICE_API_URL}/embed-text", json={"text": embedding_text})
            if vector_res.status_code == 200:
                brand_vector = vector_res.json().get("vector", [])
        except:
            pass
        
    related = await crud_product.search_by_vector(db, query_vector=brand_vector, limit=5, exclude_id=[product.id])

    return CoordinationResponse(
        answer=f"'{product.name}'와 비슷한 스타일({', '.join(style_keywords)})의 다른 브랜드 상품들입니다.",
        products=[ProductResponse.model_validate(p) for p in related]
    )