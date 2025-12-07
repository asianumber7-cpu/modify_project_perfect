from typing import List, Optional, Any, Union, Dict
from datetime import datetime
from sqlalchemy import select, update, func, text, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate 

class CRUDProduct:
    # 기본 CRUD 메서드
    async def get(self, db: AsyncSession, product_id: int) -> Optional[Product]:
        stmt = select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Product]:
        stmt = select(Product).where(Product.deleted_at.is_(None)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: Union[ProductCreate, Dict[str, Any]]) -> Product:
        if isinstance(obj_in, dict): 
            create_data = obj_in
        else: 
            create_data = obj_in.model_dump(exclude_unset=True)
        db_obj = Product(**create_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: Product, obj_in: Union[ProductUpdate, Dict[str, Any]]) -> Product:
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

    async def soft_delete(self, db: AsyncSession, *, product_id: int) -> Optional[Product]:
        now = datetime.now()
        stmt = update(Product).where(Product.id == product_id).values(deleted_at=now)
        await db.execute(stmt)
        await db.commit()
        return await self.get(db, product_id)

    # -------------------------------------------------------
    #  스마트 하이브리드 검색 - 키워드 우선 + 벡터 보조
    # -------------------------------------------------------
    async def search_smart_hybrid(
        self,
        db: AsyncSession,
        query: str,
        bert_vector: Optional[List[float]] = None,
        clip_vector: Optional[List[float]] = None,
        limit: int = 12,
        filter_gender: Optional[str] = None
    ) -> List[Product]:
        """
        스마트 하이브리드 검색:
        1단계: 키워드 매칭 상품 (이름/설명에 검색어 포함)
        2단계: 벡터 유사도로 정렬
        3단계: 부족하면 벡터 검색으로 보완
        """
        
        # 기본 필터
        base_conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None)
        ]
        
        if filter_gender:
            base_conditions.append(
                or_(
                    Product.gender == filter_gender,
                    Product.gender == 'Unisex',
                    Product.gender.is_(None)
                )
            )

        final_results = []
        seen_ids = set()

        # =====================================================
        # 1단계: 키워드 정확 매칭 (최우선)
        # =====================================================
        if query and len(query.strip()) >= 2:
            # 핵심 키워드 추출 (조사 제거)
            keywords = self._extract_keywords(query)
            
            for keyword in keywords:
                if len(keyword) < 2:
                    continue
                    
                search_pattern = f"%{keyword}%"
                
                stmt = select(Product).where(
                    *base_conditions,
                    or_(
                        Product.name.ilike(search_pattern),
                        Product.description.ilike(search_pattern),
                        Product.category.ilike(search_pattern)
                    )
                )
                
                # 벡터가 있으면 벡터 유사도순, 없으면 최신순
                if bert_vector and len(bert_vector) == 768:
                    stmt = stmt.where(Product.embedding.is_not(None))
                    dist = Product.embedding.cosine_distance(bert_vector)
                    stmt = stmt.order_by(dist)
                else:
                    stmt = stmt.order_by(Product.created_at.desc())
                
                stmt = stmt.limit(limit)
                result = await db.execute(stmt)
                
                for product in result.scalars().all():
                    if product.id not in seen_ids:
                        final_results.append(product)
                        seen_ids.add(product.id)
                        
                        if len(final_results) >= limit:
                            return final_results

        # =====================================================
        # 2단계: 벡터 유사도 검색 (보완)
        # =====================================================
        if len(final_results) < limit and bert_vector and len(bert_vector) == 768:
            remaining = limit - len(final_results)
            
            stmt = select(Product).where(
                *base_conditions,
                Product.embedding.is_not(None),
                Product.id.notin_(seen_ids) if seen_ids else True
            )
            
            dist = Product.embedding.cosine_distance(bert_vector)
            stmt = stmt.order_by(dist).limit(remaining)
            
            result = await db.execute(stmt)
            
            for product in result.scalars().all():
                if product.id not in seen_ids:
                    final_results.append(product)
                    seen_ids.add(product.id)

        # =====================================================
        # 3단계: 최신 상품 Fallback
        # =====================================================
        if len(final_results) < limit:
            remaining = limit - len(final_results)
            
            stmt = select(Product).where(
                *base_conditions,
                Product.id.notin_(seen_ids) if seen_ids else True
            )
            stmt = stmt.order_by(Product.created_at.desc()).limit(remaining)
            
            result = await db.execute(stmt)
            
            for product in result.scalars().all():
                if product.id not in seen_ids:
                    final_results.append(product)
                    seen_ids.add(product.id)

        return final_results

    def _extract_keywords(self, query: str) -> List[str]:
        """검색어에서 핵심 키워드 추출 (조사 제거)"""
        import re
        
        # 불용어 정의
        stop_words = {
            "추천", "해줘", "보여줘", "찾아줘", "알려줘", "어때", 
            "사진", "이미지", "스타일", "패션", "옷", "의류",
            "남자", "여자", "남성", "여성", "용"
        }
        
        # 조사 패턴
        particle_pattern = r'(은|는|이|가|을|를|의|에|로|으로|과|와|도|만|부터|까지|에서|보다|처럼|같은|위한|에게|한테|께)$'
        
        words = query.split()
        keywords = []
        
        for word in words:
            # 조사 제거
            clean_word = re.sub(particle_pattern, '', word)
            
            # 불용어 제외, 2글자 이상
            if clean_word and len(clean_word) >= 2 and clean_word not in stop_words:
                keywords.append(clean_word)
        
        # 원본 쿼리도 키워드로 추가 (복합어 검색용)
        full_query = query.replace(" ", "")
        if len(full_query) >= 2:
            keywords.insert(0, full_query)
        
        return keywords

    # -------------------------------------------------------
    # CLIP 이미지 벡터 기반 검색 (시각적 유사도)
    # -------------------------------------------------------
    async def search_by_clip_vector(
        self, 
        db: AsyncSession, 
        clip_vector: List[float], 
        limit: int = 12,
        filter_gender: Optional[str] = None,
        exclude_category: Optional[List[str]] = None,
        exclude_id: Optional[List[int]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None
    ) -> List[Product]:
        """
        ✅ CLIP 이미지 벡터(512차원)로 시각적 유사도 검색
        - 연예인 패션 검색 등 이미지 기반 검색에 사용
        - embedding_clip 컬럼 사용
        """
        if not clip_vector or len(clip_vector) != 512:
            return []
        
        conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None),
            Product.embedding_clip.is_not(None)
        ]
        
        # 성별 필터
        if filter_gender:
            conditions.append(
                or_(
                    Product.gender == filter_gender,
                    Product.gender == 'Unisex',
                    Product.gender.is_(None)
                )
            )
        
        # 카테고리 제외
        if exclude_category:
            for cat in exclude_category:
                conditions.append(Product.category != cat)
        
        # ID 제외
        if exclude_id:
            conditions.append(Product.id.notin_(exclude_id))
        
        # 가격 범위
        if min_price is not None:
            conditions.append(Product.price >= min_price)
        if max_price is not None:
            conditions.append(Product.price <= max_price)
        
        stmt = select(Product).where(*conditions)
        
        # CLIP 벡터 코사인 거리로 정렬
        dist = Product.embedding_clip.cosine_distance(clip_vector)
        stmt = stmt.order_by(dist).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------
    # 기존 하이브리드 검색
    # -------------------------------------------------------
    async def search_hybrid(
        self, 
        db: AsyncSession, 
        bert_vector: Optional[List[float]] = None,
        clip_vector: Optional[List[float]] = None,
        limit: int = 10,
        filter_gender: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        # ✅ 추가: 제외 파라미터
        exclude_category: Optional[List[str]] = None,
        exclude_id: Optional[List[int]] = None
    ) -> List[Product]:
        """기존 하이브리드 검색 (호환성 유지) + exclude 파라미터 추가"""
        
        base_conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None)
        ]
        
        if filter_gender:
            base_conditions.append(
                or_(
                    Product.gender == filter_gender,
                    Product.gender == 'Unisex',
                    Product.gender.is_(None)
                )
            )
        if min_price is not None:
            base_conditions.append(Product.price >= min_price)
        if max_price is not None:
            base_conditions.append(Product.price <= max_price)
        
        #  카테고리 제외
        if exclude_category:
            for cat in exclude_category:
                base_conditions.append(Product.category != cat)
        
        # ID 제외
        if exclude_id:
            base_conditions.append(Product.id.notin_(exclude_id))

        # BERT 벡터 우선
        if bert_vector and len(bert_vector) == 768:
            stmt = select(Product).where(
                *base_conditions,
                Product.embedding.is_not(None)
            )
            dist = Product.embedding.cosine_distance(bert_vector)
            stmt = stmt.order_by(dist).limit(limit)
            
            result = await db.execute(stmt)
            results = list(result.scalars().all())
            if results:
                return results

        # CLIP 벡터 (512차원)
        if clip_vector and len(clip_vector) == 512:
            stmt = select(Product).where(
                *base_conditions,
                Product.embedding_clip.is_not(None)
            )
            dist = Product.embedding_clip.cosine_distance(clip_vector)
            stmt = stmt.order_by(dist).limit(limit)
            
            result = await db.execute(stmt)
            results = list(result.scalars().all())
            if results:
                return results

        # Fallback
        stmt = select(Product).where(*base_conditions)
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------
    # 벡터 검색 
    # -------------------------------------------------------
    async def search_by_vector(
        self, 
        db: AsyncSession, 
        query_vector: List[float], 
        limit: int = 10, 
        exclude_category: Optional[List[str]] = None,
        exclude_id: Optional[List[int]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        filter_gender: Optional[str] = None,
        **kwargs
    ) -> List[Product]:
        """벡터 기반 검색 (코디 추천용)"""
        if not query_vector or len(query_vector) == 0:
            return await self.get_multi(db, limit=limit)
        
        conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None),
            Product.embedding.is_not(None)
        ]
        
        # 카테고리 제외
        if exclude_category:
            for cat in exclude_category:
                conditions.append(Product.category != cat)
        
        # ID 제외
        if exclude_id:
            conditions.append(Product.id.notin_(exclude_id))
        
        # 가격 범위
        if min_price is not None:
            conditions.append(Product.price >= min_price)
        if max_price is not None:
            conditions.append(Product.price <= max_price)
        
        # 성별 필터
        if filter_gender:
            conditions.append(
                or_(
                    Product.gender == filter_gender,
                    Product.gender == 'Unisex',
                    Product.gender.is_(None)
                )
            )
        
        stmt = select(Product).where(*conditions)
        
        dist = Product.embedding.cosine_distance(query_vector)
        stmt = stmt.order_by(dist).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    # -------------------------------------------------------
    # 키워드 검색
    # -------------------------------------------------------
    async def search_keyword(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 10, 
        filter_gender: Optional[str] = None
    ) -> List[Product]:
        """키워드 검색"""
        search_pattern = f"%{query}%"
        stmt = select(Product).where(
            Product.is_active == True,
            Product.deleted_at.is_(None),
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
                Product.category.ilike(search_pattern)
            )
        )
        if filter_gender:
            stmt = stmt.where(
                or_(
                    Product.gender == filter_gender,
                    Product.gender == 'Unisex',
                    Product.gender.is_(None)
                )
            )
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

crud_product = CRUDProduct()