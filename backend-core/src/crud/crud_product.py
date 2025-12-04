from typing import List, Optional, Any, Union, Dict
from datetime import datetime
from sqlalchemy import select, update, func, text, case # [필수] case 추가
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate 

class CRUDProduct:
    """상품 모델에 대한 비동기 CRUD 및 벡터 검색 연산을 담당하는 클래스"""

    # --- [기존 CRUD 함수들 유지] ---
    async def get(self, db: AsyncSession, product_id: int) -> Optional[Product]:
        stmt = select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Product]:
        stmt = select(Product).where(Product.deleted_at.is_(None)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: Union[ProductCreate, Dict[str, Any]]) -> Product:
        if isinstance(obj_in, dict): create_data = obj_in
        else: create_data = obj_in.model_dump(exclude_unset=True)
        db_obj = Product(**create_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: Product, obj_in: Union[ProductUpdate, Dict[str, Any]]) -> Product:
        if isinstance(obj_in, dict): update_data = obj_in
        else: update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items(): setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(self, db: AsyncSession, *, product_id: int) -> Product:
        now = datetime.now()
        stmt = update(Product).where(Product.id == product_id).values(deleted_at=now)
        await db.execute(stmt)
        await db.commit()
        return await self.get(db, product_id)

    # -------------------------------------------------------
    # 🔍 [UPGRADE] 벡터 검색 + 성별 우선 정렬 로직 적용
    # -------------------------------------------------------
    async def search_by_vector(
        self, 
        db: AsyncSession, 
        query_vector: List[float], 
        limit: int = 10,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        exclude_id: Optional[List[int]] = None,
        exclude_category: Optional[List[str]] = None,
        filter_gender: Optional[str] = None,  
        threshold: float = 1.2 
    ) -> List[Product]:
        """
        벡터 유사도 기반 상품 검색 (성별 일치 우선 정렬 적용)
        """
        # 1. 거리 계산식 (L2 Distance)
        distance_col = Product.embedding.l2_distance(query_vector)
        
        # 2. 기본 쿼리 시작
        stmt = select(Product)
        
        # 3. [핵심] 정렬 로직 개선 (성별 우선 -> 그 다음 벡터 거리)
        if filter_gender:
            # "요청한 성별과 정확히 일치하면 0등, 아니면(Unisex) 1등"으로 정렬
            gender_priority = case(
                (Product.gender == filter_gender, 0),
                else_=1
            )
            stmt = stmt.order_by(gender_priority, distance_col)
        else:
            # 성별 조건 없으면 그냥 벡터 거리순
            stmt = stmt.order_by(distance_col)
        
        # 4. 필터링 (Where 조건)
        stmt = stmt.filter(Product.is_active == True)
        stmt = stmt.filter(Product.deleted_at.is_(None))
        stmt = stmt.filter(Product.embedding.is_not(None))
        
        # 성별 필터 (Male 요청 시 -> Male 또는 Unisex만 포함)
        if filter_gender:
            stmt = stmt.filter(
                (Product.gender == filter_gender) | (Product.gender == 'Unisex')
            )

        # 유사도 커트라인
        stmt = stmt.filter(distance_col < threshold)

        # 추가 필터
        if min_price is not None: stmt = stmt.filter(Product.price >= min_price)
        if max_price is not None: stmt = stmt.filter(Product.price <= max_price)
        if exclude_id and len(exclude_id) > 0: 
            stmt = stmt.filter(Product.id.notin_(exclude_id))
        if exclude_category and len(exclude_category) > 0: 
            stmt = stmt.filter(Product.category.notin_(exclude_category))

        # 개수 제한
        stmt = stmt.limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

# 싱글톤 객체 생성
crud_product = CRUDProduct()