import json 
from datetime import datetime
from typing import List, Optional, Any, Union, Dict
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate 

class CRUDProduct:
    """상품 모델에 대한 비동기 CRUD 및 벡터 검색 연산을 담당하는 클래스"""

    # -------------------------------------------------------
    # [기존 코드 유지] 기본 CRUD 기능
    # -------------------------------------------------------
    async def get(self, db: AsyncSession, product_id: int) -> Optional[Product]:
        """ID로 상품 하나를 조회합니다 (Soft deleted 제외)."""
        stmt = select(Product).where(
            Product.id == product_id, 
            Product.deleted_at.is_(None)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """상품 목록을 조회합니다 (Soft deleted 제외)."""
        stmt = select(Product).where(Product.deleted_at.is_(None)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: Union[ProductCreate, Dict[str, Any]]) -> Product:
        """새로운 상품을 생성합니다."""
        if isinstance(obj_in, dict):
            create_data = obj_in
        else:
            create_data = obj_in.model_dump(exclude_unset=True)
            
        db_obj = Product(**create_data)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: Product, obj_in: Union[ProductUpdate, Dict[str, Any]]
    ) -> Product:
        """상품 정보를 업데이트합니다."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(self, db: AsyncSession, *, product_id: int) -> Product:
        """상품을 소프트 삭제 처리합니다."""
        now = datetime.now()
        # 존재 여부 확인 및 객체 가져오기
        result = await db.execute(select(Product).where(Product.id == product_id))
        db_obj = result.scalars().first()
        
        if not db_obj:
            raise Exception("Product not found") 

        stmt = update(Product).where(Product.id == product_id).values(deleted_at=now)
        await db.execute(stmt)
        await db.commit()
        
        # 갱신된 객체 반환을 위해 속성 업데이트
        setattr(db_obj, 'deleted_at', now) 
        return db_obj

    # -------------------------------------------------------
    # [새로 추가된 코드] 에러 해결을 위한 벡터 검색 함수
    # -------------------------------------------------------
    async def search_by_vector(
        self, 
        db: AsyncSession, 
        query_vector: List[float], 
        limit: int = 10,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        exclude_id: Optional[List[int]] = None,
        exclude_category: Optional[List[str]] = None
    ) -> List[Product]:
        """
        [AI Core] 벡터 유사도(L2 Distance/Cosine) 기반 상품 검색
        """
        # 1. 유사도 정렬 (Product.embedding 컬럼이 pgvector 타입이어야 함)
        # l2_distance (유클리드 거리) 혹은 cosine_distance 사용
        # 여기서는 가장 일반적인 l2_distance를 사용합니다. (거리가 가까울수록 유사)
        stmt = select(Product).order_by(Product.embedding.l2_distance(query_vector))
        
        # 2. 기본 필터 (삭제된 것, 비활성, 임베딩 없는 것 제외)
        stmt = stmt.filter(Product.is_active == True)
        stmt = stmt.filter(Product.deleted_at.is_(None))
        stmt = stmt.filter(Product.embedding.is_not(None))

        # 3. 추가 필터링 (가격, 카테고리 등)
        if min_price is not None:
            stmt = stmt.filter(Product.price >= min_price)
        
        if max_price is not None:
            stmt = stmt.filter(Product.price <= max_price)
            
        if exclude_id:
            stmt = stmt.filter(Product.id.notin_(exclude_id))
            
        if exclude_category:
            stmt = stmt.filter(Product.category.notin_(exclude_category))

        # 4. 개수 제한
        stmt = stmt.limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

# 싱글톤 객체 생성
crud_product = CRUDProduct()