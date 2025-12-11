
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Numeric, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.models.base import Base


class OrderStatus(str, enum.Enum):
    """주문 상태"""
    PENDING = "pending"         # 대기중
    CONFIRMED = "confirmed"     # 확인됨
    SHIPPING = "shipping"       # 배송중
    DELIVERED = "delivered"     # 배송완료
    CANCELLED = "cancelled"     # 취소됨


class Order(Base):
    """주문 테이블"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 주문 번호 (고유)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # 사용자 (외래키)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 주문 상태
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING.value)
    
    # 총 금액
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    
    # 배송 정보
    shipping_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shipping_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # 메모
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    user = relationship("User", backref="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """주문 상품 테이블"""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 주문 (외래키)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    
    # 상품 (외래키)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    
    # 상품 정보 스냅샷 (주문 시점의 정보 저장)
    product_name: Mapped[str] = mapped_column(String(255))
    product_price: Mapped[int] = mapped_column(Integer)
    product_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # 수량
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    # 소계
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    
    # 관계 설정
    order = relationship("Order", back_populates="items")
    product = relationship("Product")