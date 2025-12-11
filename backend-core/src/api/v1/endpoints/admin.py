from typing import Any, List, Optional, Literal
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import logging
import json
import re

from src.schemas.email import EmailBroadcastRequest, EmailStatusResponse 
from src.core.celery_app import broadcast_email_task 
from src.api.deps import get_db, get_current_user
from src.schemas.admin import DashboardStatsResponse, SalesData
from src.models.user import User
from src.schemas.product import ProductCreate
from src.crud.crud_product import crud_product

router = APIRouter()
logger = logging.getLogger(__name__)

# AI Service URL
AI_SERVICE_URL = "http://ai-service-api:8000"

def check_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user doesn't have enough privileges"
        )
    return current_user

def _fix_encoding(text: str) -> str:
    """[핵심] AI 응답의 깨진 한글 및 유니코드 복구"""
    if not text:
        return ""
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        pass
    try:
        return text.encode('utf-8').decode('unicode_escape')
    except:
        pass
    return text

def _ensure_vector_dim(vector: Optional[List[float]], dim: int) -> List[float]:
    """[방어 로직] 벡터 차원 강제 보정 (DB 에러 방지)"""
    if not vector or len(vector) == 0:
        return [0.0] * dim
    
    current_len = len(vector)
    if current_len == dim:
        return vector
    
    if current_len < dim:
        return vector + [0.0] * (dim - current_len)
    else:
        return vector[:dim]

@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_admin_dashboard_stats(
    time_range: Literal["daily", "weekly", "monthly"] = Query("weekly"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_superuser),
) -> Any:
    # [Mock Data]
    sales_trend = []
    if time_range == "weekly":
        sales_trend = [
            {"label": "월", "value": 120}, {"label": "화", "value": 190}, 
            {"label": "수", "value": 300}, {"label": "목", "value": 500}, 
            {"label": "금", "value": 200}, {"label": "토", "value": 300}, 
            {"label": "일", "value": 450}
        ]
    elif time_range == "monthly":
         sales_trend = [
            {"label": "1주", "value": 1500}, {"label": "2주", "value": 2200}, 
            {"label": "3주", "value": 1800}, {"label": "4주", "value": 3100}
        ]
    else: # daily
         sales_trend = [
            {"label": "00시", "value": 5}, {"label": "04시", "value": 15}, 
            {"label": "08시", "value": 40}, {"label": "12시", "value": 80}, 
            {"label": "16시", "value": 60}, {"label": "20시", "value": 110},
        ]
    
    category_data = [
        {"label": "Outer", "value": 35}, 
        {"label": "Top", "value": 40}, 
        {"label": "Bottom", "value": 15}, 
        {"label": "Shoes", "value": 10}
    ]

    return DashboardStatsResponse(
        total_revenue=12450000.0,
        new_orders=45,
        visitors=1230,
        growth_rate=12.5,
        weekly_sales_trend=[SalesData(**d) for d in sales_trend],
        category_sales_pie=[SalesData(**d) for d in category_data]
    )

@router.post("/broadcast-email", response_model=EmailStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_broadcast_email(
    email_req: EmailBroadcastRequest,
    current_user: User = Depends(check_superuser),
) -> Any:
    task = broadcast_email_task.delay(
        subject=email_req.subject,
        body=email_req.body,
        filter_type=email_req.recipients_filter
    )
    return EmailStatusResponse(
        message="Broadcast email functionality has been triggered successfully.",
        task_id=str(task.id)
    )

@router.post("/products/upload-ai", status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_superuser),
) -> Any:
    """
    [관리자] 이미지 업로드 -> AI 분석 -> DB 자동 등록
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    ai_response = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await file.seek(0)
            files = {"file": (file.filename, await file.read(), file.content_type)}
            
            logger.info(f"📤 Sending image to AI Service: {file.filename}")
            response = await client.post(f"{AI_SERVICE_URL}/api/v1/analyze-image", files=files)
            
            if response.status_code != 200:
                logger.error(f"❌ AI Service Error: {response.text}")
                # AI가 죽어있어도 프로세스는 계속 진행하기 위해 더미 데이터 생성 가능하지만
                # 여기서는 에러를 명시하고 중단합니다.
                raise HTTPException(status_code=502, detail="AI 분석 서비스 응답 오류")
            
            ai_response = response.json()
            
    except httpx.RequestError as exc:
        logger.error(f"❌ AI Connection Failed: {exc}")
        raise HTTPException(status_code=503, detail=f"AI 서비스 연결 실패: {exc}")

    try:
        # (1) 텍스트 인코딩 복구
        name = _fix_encoding(ai_response.get("name", "AI Uploaded Product"))
        description = _fix_encoding(ai_response.get("description", "AI analyzing..."))
        category = _fix_encoding(ai_response.get("category", "Uncategorized"))
        gender = ai_response.get("gender", "Unisex")
        
        # (2) 벡터 차원 방어 로직 (DB 에러 원천 차단)
        raw_bert = ai_response.get("vector", [])
        safe_bert = _ensure_vector_dim(raw_bert, 768)
        
        raw_clip = ai_response.get("vector_clip", [])
        safe_clip = _ensure_vector_dim(raw_clip, 512)
        
        raw_upper = ai_response.get("vector_clip_upper", [])
        safe_upper = _ensure_vector_dim(raw_upper, 512)
        
        raw_lower = ai_response.get("vector_clip_lower", [])
        safe_lower = _ensure_vector_dim(raw_lower, 512)

        product_in = ProductCreate(
            name=name,
            description=description,
            price=ai_response.get("price", 0),
            stock_quantity=100,
            category=category,
            gender=gender,
            image_url=f"/static/images/{file.filename}", 
            is_active=True,
            embedding=safe_bert,
            embedding_clip=safe_clip,
            embedding_clip_upper=safe_upper,
            embedding_clip_lower=safe_lower
        )

        product = await crud_product.create(db, obj_in=product_in)
        logger.info(f"✅ Product Created: {product.name} (ID: {product.id})")
        return product

    except Exception as e:
        logger.error(f"❌ DB Save Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"데이터 저장 실패: {str(e)}")