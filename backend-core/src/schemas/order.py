
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPING = "shipping"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# --- 주문 상품 스키마 ---
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_price: int
    product_image: Optional[str] = None
    quantity: int
    subtotal: int

    model_config = ConfigDict(from_attributes=True)


# --- 주문 스키마 ---
class OrderBase(BaseModel):
    shipping_address: Optional[str] = None
    shipping_name: Optional[str] = None
    shipping_phone: Optional[str] = None
    note: Optional[str] = None


class OrderCreate(OrderBase):
    items: List[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderResponse(OrderBase):
    id: int
    order_number: str
    user_id: int
    status: str
    total_amount: int
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- 주문 목록 응답 (관리자용) ---
class OrderListResponse(BaseModel):
    id: int
    order_number: str
    user_id: int
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    status: str
    total_amount: int
    item_count: int
    first_item_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)