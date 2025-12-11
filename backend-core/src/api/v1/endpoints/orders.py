
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.models.order import Order, OrderItem, OrderStatus
from src.models.product import Product

logger = logging.getLogger(__name__)
router = APIRouter()


def generate_order_number() -> str:
    """주문 번호 생성"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = str(uuid.uuid4())[:6].upper()
    return f"ORD-{timestamp}-{unique_id}"


# =========================================================
# [사용자] 내 주문 목록
# =========================================================
@router.get("/my", response_model=Dict[str, Any])
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
) -> Dict[str, Any]:
    """내 주문 목록 조회"""
    
    # 총 개수
    count_stmt = select(func.count(Order.id)).where(Order.user_id == current_user.id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # 페이징
    offset = (page - 1) * limit
    stmt = select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    # 응답 구성
    orders_data = []
    for order in orders:
        # 주문 상품 조회
        items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
        items_result = await db.execute(items_stmt)
        items = items_result.scalars().all()
        
        orders_data.append({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "total_amount": order.total_amount,
            "item_count": len(items),
            "first_item_name": items[0].product_name if items else None,
            "created_at": order.created_at.isoformat()
        })
    
    return {
        "orders": orders_data,
        "total": total,
        "page": page,
        "limit": limit
    }


# =========================================================
# [사용자] 주문 상세
# =========================================================
@router.get("/my/{order_id}", response_model=Dict[str, Any])
async def get_my_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """내 주문 상세 조회"""
    
    stmt = select(Order).where(and_(Order.id == order_id, Order.user_id == current_user.id))
    result = await db.execute(stmt)
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    # 주문 상품 조회
    items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": order.total_amount,
        "shipping_address": order.shipping_address,
        "shipping_name": order.shipping_name,
        "shipping_phone": order.shipping_phone,
        "note": order.note,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_price": item.product_price,
                "product_image": item.product_image,
                "quantity": item.quantity,
                "subtotal": item.subtotal
            }
            for item in items
        ]
    }


# =========================================================
# [사용자] 주문 생성
# =========================================================
@router.post("/", response_model=Dict[str, Any])
async def create_order(
    order_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """주문 생성"""
    
    items = order_data.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="주문 상품이 없습니다.")
    
    # 주문 생성
    order = Order(
        order_number=generate_order_number(),
        user_id=current_user.id,
        status=OrderStatus.PENDING.value,
        shipping_address=order_data.get("shipping_address"),
        shipping_name=order_data.get("shipping_name"),
        shipping_phone=order_data.get("shipping_phone"),
        note=order_data.get("note"),
    )
    
    db.add(order)
    await db.flush()  # ID 생성
    
    # 주문 상품 추가
    total_amount = 0
    for item in items:
        # 상품 조회
        product_stmt = select(Product).where(Product.id == item["product_id"])
        product_result = await db.execute(product_stmt)
        product = product_result.scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"상품 ID {item['product_id']}를 찾을 수 없습니다.")
        
        quantity = item.get("quantity", 1)
        subtotal = product.price * quantity
        total_amount += subtotal
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            product_price=product.price,
            product_image=product.image_url,
            quantity=quantity,
            subtotal=subtotal
        )
        db.add(order_item)
    
    order.total_amount = total_amount
    
    await db.commit()
    await db.refresh(order)
    
    logger.info(f"✅ Order {order.order_number} created by user {current_user.id}")
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "total_amount": order.total_amount,
        "status": order.status
    }


# =========================================================
# 🆕 [관리자] 주문 목록 조회
# =========================================================
@router.get("/admin", response_model=Dict[str, Any])
async def get_orders_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="주문 상태 필터"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    주문 목록 조회 (관리자 전용)
    - 상태 필터, 날짜 범위 필터 지원
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    conditions = []
    
    # 상태 필터
    if status and status != "all":
        conditions.append(Order.status == status)
    
    # 날짜 필터
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            conditions.append(Order.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            conditions.append(Order.created_at <= end_dt)
        except ValueError:
            pass
    
    # 총 개수
    count_stmt = select(func.count(Order.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # 통계 계산
    # 총 매출
    revenue_stmt = select(func.sum(Order.total_amount))
    revenue_result = await db.execute(revenue_stmt)
    total_revenue = revenue_result.scalar() or 0
    
    # 총 주문 수
    all_orders_stmt = select(func.count(Order.id))
    all_orders_result = await db.execute(all_orders_stmt)
    total_orders = all_orders_result.scalar() or 0
    
    # 평균 주문액
    avg_order = int(total_revenue / total_orders) if total_orders > 0 else 0
    
    # 처리 대기
    pending_stmt = select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING.value)
    pending_result = await db.execute(pending_stmt)
    pending_count = pending_result.scalar() or 0
    
    # 페이징
    offset = (page - 1) * limit
    stmt = select(Order)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    # 응답 구성
    orders_data = []
    for order in orders:
        # 사용자 정보
        user_stmt = select(User).where(User.id == order.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        # 주문 상품
        items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
        items_result = await db.execute(items_stmt)
        items = items_result.scalars().all()
        
        orders_data.append({
            "id": order.id,
            "order_number": order.order_number,
            "user_id": order.user_id,
            "user_email": user.email if user else None,
            "user_name": user.full_name if user else None,
            "status": order.status,
            "total_amount": order.total_amount,
            "item_count": len(items),
            "first_item_name": items[0].product_name if items else None,
            "shipping_name": order.shipping_name,
            "shipping_phone": order.shipping_phone,
            "created_at": order.created_at.isoformat(),
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "product_price": item.product_price,
                    "quantity": item.quantity,
                    "subtotal": item.subtotal
                }
                for item in items
            ]
        })
    
    return {
        "orders": orders_data,
        "total": total,
        "page": page,
        "limit": limit,
        "stats": {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "avg_order": avg_order,
            "pending": pending_count
        }
    }


# =========================================================
# 🆕 [관리자] 주문 상태 변경
# =========================================================
@router.patch("/admin/{order_id}/status", response_model=Dict[str, Any])
async def update_order_status(
    order_id: int,
    status_data: Dict[str, str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """주문 상태 변경 (관리자 전용)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    new_status = status_data.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="상태값이 필요합니다.")
    
    # 유효한 상태인지 확인
    valid_statuses = [s.value for s in OrderStatus]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 상태입니다. 가능한 값: {valid_statuses}")
    
    # 주문 조회
    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    old_status = order.status
    order.status = new_status
    
    await db.commit()
    await db.refresh(order)
    
    logger.info(f"📦 Order {order.order_number} status changed: {old_status} → {new_status}")
    
    return {
        "success": True,
        "order_id": order.id,
        "order_number": order.order_number,
        "old_status": old_status,
        "new_status": new_status
    }


# =========================================================
# 🆕 [관리자] 주문 상세 조회
# =========================================================
@router.get("/admin/{order_id}", response_model=Dict[str, Any])
async def get_order_detail_admin(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """주문 상세 조회 (관리자 전용)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    # 사용자 정보
    user_stmt = select(User).where(User.id == order.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    
    # 주문 상품
    items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "user": {
            "id": user.id if user else None,
            "email": user.email if user else None,
            "name": user.full_name if user else None,
            "phone": user.phone_number if user else None
        },
        "status": order.status,
        "total_amount": order.total_amount,
        "shipping_address": order.shipping_address,
        "shipping_name": order.shipping_name,
        "shipping_phone": order.shipping_phone,
        "note": order.note,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_price": item.product_price,
                "product_image": item.product_image,
                "quantity": item.quantity,
                "subtotal": item.subtotal
            }
            for item in items
        ]
    }