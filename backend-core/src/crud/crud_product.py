from typing import List, Optional, Any, Union, Dict
from datetime import datetime
from sqlalchemy import select, update, func, text, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate 

class CRUDProduct:
    # 기본 CRUD 메서드 유지
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
    # 🔍 [UPGRADE] Hybrid Search (BERT + CLIP)
    # -------------------------------------------------------
    async def search_hybrid(
        self, 
        db: AsyncSession, 
        bert_vector: Optional[List[float]] = None,
        clip_vector: Optional[List[float]] = None,
        limit: int = 10,
        filter_gender: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None
    ) -> List[Product]:
        """
        Hybrid Search: CLIP(0.7) + BERT(0.3) 가중치 적용
        """
        stmt = select(Product)
        
        # 1. 거리 계산 (Cosine Distance)
        if bert_vector and clip_vector:
            dist_bert = Product.embedding.cosine_distance(bert_vector)
            dist_clip = Product.embedding_clip.cosine_distance(clip_vector)
            
            # [튜닝] 이미지 유사도(CLIP)
            combined_dist = (dist_bert * 0.1) + (dist_clip * 0.9)
            stmt = stmt.order_by(combined_dist)
            
            stmt = stmt.filter(Product.embedding.is_not(None))
            stmt = stmt.filter(Product.embedding_clip.is_not(None))
            
        elif bert_vector:
            dist = Product.embedding.cosine_distance(bert_vector)
            stmt = stmt.order_by(dist).filter(Product.embedding.is_not(None))
            
        elif clip_vector:
            dist = Product.embedding_clip.cosine_distance(clip_vector)
            stmt = stmt.order_by(dist).filter(Product.embedding_clip.is_not(None))
            
        else:
            return await self.get_multi(db, limit=limit)

        # 2. 성별 필터링
        if filter_gender:
            stmt = stmt.filter(
                (Product.gender == filter_gender) | (Product.gender == 'Unisex')
            )

        # 3. 기본 필터링
        stmt = stmt.filter(Product.is_active == True)
        stmt = stmt.filter(Product.deleted_at.is_(None))

        if min_price is not None: stmt = stmt.filter(Product.price >= min_price)
        if max_price is not None: stmt = stmt.filter(Product.price <= max_price)

        stmt = stmt.limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    # Legacy Support
    async def search_by_vector(self, db: AsyncSession, query_vector: List[float], limit: int = 10, **kwargs):
        return await self.search_hybrid(db, bert_vector=query_vector, limit=limit, **kwargs)
    
    # Keyword Fallback
    async def search_keyword(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 10, 
        filter_gender: Optional[str] = None
    ) -> List[Product]:
        search_pattern = f"%{query}%"
        stmt = select(Product).where(
            Product.is_active == True,
            Product.deleted_at.is_(None),
            (
                Product.name.ilike(search_pattern) | 
                Product.description.ilike(search_pattern) | 
                Product.category.ilike(search_pattern)
            )
        )
        if filter_gender:
            stmt = stmt.where((Product.gender == filter_gender) | (Product.gender == 'Unisex'))
            
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

crud_product = CRUDProduct()