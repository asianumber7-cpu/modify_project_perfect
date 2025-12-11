from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, TIMESTAMP, Text, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from src.db.session import Base 
from src.config.settings import settings
from src.constants import ProductCategory

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # 성별 필터링
    gender: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)

    # [Existing] BERT Vector (768차원 - Text Context)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(768))

    # [Existing] CLIP Vector (512차원 - Visual Context, 전체 이미지)
    embedding_clip: Mapped[Optional[List[float]]] = mapped_column(Vector(512))

    # ✅ [NEW] CLIP Upper Vector (512차원 - 상의 영역)
    embedding_clip_upper: Mapped[Optional[List[float]]] = mapped_column(Vector(512))

    # ✅ [NEW] CLIP Lower Vector (512차원 - 하의 영역)
    embedding_clip_lower: Mapped[Optional[List[float]]] = mapped_column(Vector(512))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    @property
    def in_stock(self) -> bool:
        return self.stock_quantity > 0

    __table_args__ = (
        CheckConstraint('price >= 0', name='check_price_positive'),
        CheckConstraint('stock_quantity >= 0', name='check_stock_positive'),
        CheckConstraint("gender IN ('Male', 'Female', 'Unisex', NULL)", name='check_gender_valid'),
        CheckConstraint(f"category IN {tuple(ProductCategory.list())}", name='check_category_valid'),
        # BERT Index
        Index(
            'ix_product_embedding_hnsw',
            'embedding',
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 128},
            postgresql_ops={'embedding': 'vector_cosine_ops'},
            postgresql_where=text("deleted_at IS NULL")
        ),
        # CLIP Index (전체)
        Index(
            'ix_product_embedding_clip_hnsw',
            'embedding_clip',
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 128},
            postgresql_ops={'embedding_clip': 'vector_cosine_ops'},
            postgresql_where=text("deleted_at IS NULL")
        ),
        # ✅ [NEW] CLIP Upper Index (상의)
        Index(
            'ix_product_embedding_clip_upper_hnsw',
            'embedding_clip_upper',
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 128},
            postgresql_ops={'embedding_clip_upper': 'vector_cosine_ops'},
            postgresql_where=text("deleted_at IS NULL")
        ),
        # ✅ [NEW] CLIP Lower Index (하의)
        Index(
            'ix_product_embedding_clip_lower_hnsw',
            'embedding_clip_lower',
            postgresql_using='hnsw',
            postgresql_with={'m': 32, 'ef_construction': 128},
            postgresql_ops={'embedding_clip_lower': 'vector_cosine_ops'},
            postgresql_where=text("deleted_at IS NULL")
        ),
    )