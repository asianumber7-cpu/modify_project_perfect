from typing import List, Optional, Any, Union, Dict, Tuple
from datetime import datetime
from sqlalchemy import select, update, func, text, case, or_, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate 

logger = logging.getLogger(__name__)

class CRUDProduct:
    # ===============================================================
    # 🛡️ [Fix] 벡터 안전장치 (DB 에러 방지)
    # ===============================================================
    def _validate_vector(self, vector: Optional[List[float]], dim: int) -> List[float]:
        """
        DB Insert/Update 직전 최종 벡터 검증
        - None이거나 빈 리스트면 0.0으로 채워진 벡터 반환 (DB 에러 원천 차단)
        """
        if not vector or len(vector) == 0:
            return [0.0] * dim
        
        if len(vector) != dim:
            if len(vector) < dim:
                return vector + [0.0] * (dim - len(vector))
            else:
                return vector[:dim]
        return vector

    # ===============================================================
    # ✅ [NEW] 유사도 계산 헬퍼
    # ===============================================================
    def _distance_to_similarity(self, distance: float) -> float:
        """
        코사인 거리를 유사도 점수로 변환
        - cosine_distance: 0 (동일) ~ 2 (정반대)
        - similarity: 1.0 (동일) ~ 0.0 (정반대)
        """
        # 코사인 거리 = 1 - 코사인 유사도
        # 따라서 유사도 = 1 - 거리
        similarity = max(0.0, min(1.0, 1.0 - distance))
        return round(similarity, 4)

    def _attach_similarity(self, product: Product, distance: Optional[float]) -> Product:
        """Product 객체에 similarity 속성 동적 추가"""
        if distance is not None:
            product.similarity = self._distance_to_similarity(distance)
        else:
            product.similarity = None
        return product

    # ===============================================================
    # ⚙️ 기본 CRUD
    # ===============================================================
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
        
        # [Fix] 벡터 검증 및 보정 적용
        if "embedding" in create_data:
            create_data["embedding"] = self._validate_vector(create_data.get("embedding"), 768)
        if "embedding_clip" in create_data:
            create_data["embedding_clip"] = self._validate_vector(create_data.get("embedding_clip"), 512)
        if "embedding_clip_upper" in create_data:
            create_data["embedding_clip_upper"] = self._validate_vector(create_data.get("embedding_clip_upper"), 512)
        if "embedding_clip_lower" in create_data:
            create_data["embedding_clip_lower"] = self._validate_vector(create_data.get("embedding_clip_lower"), 512)

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
        
        if "embedding" in update_data:
             update_data["embedding"] = self._validate_vector(update_data["embedding"], 768)

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

    # ===============================================================
    # 🗑️ [NEW] 하드 삭제 (완전 삭제)
    # ===============================================================
    async def hard_delete(self, db: AsyncSession, *, product_id: int) -> bool:
        """
        상품을 DB에서 완전히 삭제합니다.
        - 벡터 데이터도 함께 삭제됨
        - 이미지 파일 삭제는 API 레이어에서 처리
        """
        stmt = delete(Product).where(Product.id == product_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    # ===============================================================
    # 🔍 검색 로직
    # ===============================================================

    # -------------------------------------------------------
    # 1. ✅ [FIX] 스마트 하이브리드 검색 (similarity 반환)
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
        
        base_conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None)
        ]
        
        # ✅ [FIX] 성별 필터 조건 (별도 보관)
        gender_condition = None
        if filter_gender:
            gender_condition = or_(
                Product.gender == filter_gender,
                Product.gender == 'Unisex',
                Product.gender.is_(None)
            )
            base_conditions.append(gender_condition)
            logger.info(f"🎯 Gender filter applied: {filter_gender}")

        final_results = []
        seen_ids = set()

        # [Step 1] 키워드 매칭 (with similarity)
        keyword_found = False
        if query and len(query.strip()) >= 1:
            keywords = self._extract_keywords(query)
            logger.info(f"🔑 Extracted keywords: {keywords}")
            
            for keyword in keywords:
                if len(keyword) < 1: continue
                search_pattern = f"%{keyword}%"
                
                # 벡터가 있으면 distance 계산
                if bert_vector and len(bert_vector) == 768:
                    dist = Product.embedding.cosine_distance(bert_vector)
                    stmt = select(Product, dist.label('distance')).where(
                        *base_conditions,
                        Product.embedding.is_not(None),
                        or_(
                            Product.name.ilike(search_pattern),
                            Product.description.ilike(search_pattern),
                            Product.category.ilike(search_pattern)
                        )
                    ).order_by(dist).limit(limit)
                else:
                    # 벡터 없으면 distance = None
                    stmt = select(Product, text('NULL as distance')).where(
                        *base_conditions,
                        or_(
                            Product.name.ilike(search_pattern),
                            Product.description.ilike(search_pattern),
                            Product.category.ilike(search_pattern)
                        )
                    ).order_by(Product.created_at.desc()).limit(limit)
                
                result = await db.execute(stmt)
                rows = result.all()
                
                for row in rows:
                    product = row[0]
                    distance = row[1] if len(row) > 1 else None
                    
                    if product.id not in seen_ids:
                        self._attach_similarity(product, distance)
                        final_results.append(product)
                        seen_ids.add(product.id)
                        keyword_found = True

        # [Fix] 키워드로 찾은 게 있으면 여기서 종료 (정확도 우선)
        if keyword_found and len(final_results) > 0:
            logger.info(f"✅ Keyword search found {len(final_results)} products")
            return final_results

        # [Step 2] 벡터 검색 (키워드 결과 없을 때만 Fallback)
        if len(final_results) == 0 and bert_vector and len(bert_vector) == 768:
            logger.info(f"🔄 Falling back to vector search")
            
            dist = Product.embedding.cosine_distance(bert_vector)
            stmt = select(Product, dist.label('distance')).where(
                *base_conditions,
                Product.embedding.is_not(None),
                Product.id.notin_(seen_ids) if seen_ids else True
            ).order_by(dist).limit(limit)
            
            result = await db.execute(stmt)
            rows = result.all()
            
            for row in rows:
                product = row[0]
                distance = row[1] if len(row) > 1 else None
                
                if product.id not in seen_ids:
                    self._attach_similarity(product, distance)
                    final_results.append(product)
                    seen_ids.add(product.id)

        return final_results

    def _extract_keywords(self, query: str) -> List[str]:
        import re
        stop_words = {"추천", "해줘", "보여줘", "찾아줘", "알려줘", "어때", "사진", "이미지", "스타일", "패션", "옷"}
        particle_pattern = r'(은|는|이|가|을|를|의|에|로|으로|과|와|도|만)$'
        words = query.split()
        keywords = []
        for word in words:
            clean_word = re.sub(particle_pattern, '', word)
            if clean_word and len(clean_word) >= 2 and clean_word not in stop_words:
                keywords.append(clean_word)
        full_query = query.replace(" ", "")
        if len(full_query) >= 1: keywords.insert(0, full_query)
        return keywords

    # -------------------------------------------------------
    # 2. ✅ [FIX] CLIP 이미지 벡터 검색 (similarity 반환)
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
        max_price: Optional[int] = None,
        target: str = "full",
        include_category: Optional[List[str]] = None
    ) -> List[Product]:
        
        # 벡터 없으면 빈 결과
        if not clip_vector or len(clip_vector) != 512:
            return []
        
        # [Fix] 타겟에 따른 비교 컬럼 결정
        target_column = Product.embedding_clip # Default
        
        if target == "upper":
            target_column = Product.embedding_clip_upper
            logger.info("🎯 Searching against UPPER body vectors")
        elif target == "lower":
            target_column = Product.embedding_clip_lower
            logger.info("🎯 Searching against LOWER body vectors")
        else:
            logger.info("🎯 Searching against FULL body vectors")

        # 필터 조건 구성
        conditions = [
            Product.is_active == True,
            Product.deleted_at.is_(None),
            target_column.is_not(None) # 해당 컬럼 데이터 존재 필수
        ]

        if include_category:
            conditions.append(Product.category.in_(include_category))
        
        # ✅ [FIX] 성별 필터 로깅 추가
        if filter_gender:
            conditions.append(or_(Product.gender == filter_gender, Product.gender == 'Unisex', Product.gender.is_(None)))
            logger.info(f"🎯 CLIP search with gender filter: {filter_gender}")
        
        if exclude_category:
            for cat in exclude_category: conditions.append(Product.category != cat)
        if exclude_id: conditions.append(Product.id.notin_(exclude_id))
        if min_price: conditions.append(Product.price >= min_price)
        if max_price: conditions.append(Product.price <= max_price)
        
        # 거리 계산
        dist = target_column.cosine_distance(clip_vector)
        
        stmt = select(Product, dist.label('distance')).where(*conditions)
        stmt = stmt.order_by(dist).limit(limit)
        
        result = await db.execute(stmt)
        rows = result.all()
        
        # ✅ [FIX] similarity 속성 추가해서 반환
        products = []
        for row in rows:
            product = row[0]
            distance = row[1] if len(row) > 1 else None
            self._attach_similarity(product, distance)
            products.append(product)
        
        logger.info(f"✅ CLIP vector search found {len(products)} products")
        return products

    # -------------------------------------------------------
    # 3. ✅ [FIX] 기존 검색 메서드 (호환성 유지 + similarity)
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
        exclude_category: Optional[List[str]] = None, 
        exclude_id: Optional[List[int]] = None
    ) -> List[Product]:
        
        base_conditions = [Product.is_active == True, Product.deleted_at.is_(None)]
        
        if filter_gender: 
            base_conditions.append(or_(Product.gender == filter_gender, Product.gender == 'Unisex', Product.gender.is_(None)))
            logger.info(f"🎯 Hybrid search with gender filter: {filter_gender}")
        
        if min_price: base_conditions.append(Product.price >= min_price)
        if max_price: base_conditions.append(Product.price <= max_price)
        if exclude_category:
            for cat in exclude_category: base_conditions.append(Product.category != cat)
        if exclude_id: base_conditions.append(Product.id.notin_(exclude_id))

        # BERT 벡터 검색
        if bert_vector and len(bert_vector) == 768:
            dist = Product.embedding.cosine_distance(bert_vector)
            stmt = select(Product, dist.label('distance')).where(
                *base_conditions, 
                Product.embedding.is_not(None)
            ).order_by(dist).limit(limit)
            
            result = await db.execute(stmt)
            rows = result.all()
            
            if rows:
                products = []
                for row in rows:
                    product = row[0]
                    distance = row[1] if len(row) > 1 else None
                    self._attach_similarity(product, distance)
                    products.append(product)
                return products
        
        # CLIP 벡터 검색 Fallback
        if clip_vector and len(clip_vector) == 512:
            dist = Product.embedding_clip.cosine_distance(clip_vector)
            stmt = select(Product, dist.label('distance')).where(
                *base_conditions, 
                Product.embedding_clip.is_not(None)
            ).order_by(dist).limit(limit)
            
            result = await db.execute(stmt)
            rows = result.all()
            
            if rows:
                products = []
                for row in rows:
                    product = row[0]
                    distance = row[1] if len(row) > 1 else None
                    self._attach_similarity(product, distance)
                    products.append(product)
                return products

        # 최신순 Fallback
        stmt = select(Product).where(*base_conditions).order_by(Product.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        products = list(result.scalars().all())
        
        # Fallback 결과에는 similarity 없음
        for p in products:
            p.similarity = None
        
        return products

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
        
        if not query_vector: 
            return await self.get_multi(db, limit=limit)
        
        conditions = [Product.is_active == True, Product.deleted_at.is_(None), Product.embedding.is_not(None)]
        
        if exclude_category:
            for cat in exclude_category: conditions.append(Product.category != cat)
        if exclude_id: conditions.append(Product.id.notin_(exclude_id))
        if min_price: conditions.append(Product.price >= min_price)
        if max_price: conditions.append(Product.price <= max_price)
        if filter_gender: 
            conditions.append(or_(Product.gender == filter_gender, Product.gender == 'Unisex', Product.gender.is_(None)))

        dist = Product.embedding.cosine_distance(query_vector)
        stmt = select(Product, dist.label('distance')).where(*conditions).order_by(dist).limit(limit)
        
        result = await db.execute(stmt)
        rows = result.all()
        
        products = []
        for row in rows:
            product = row[0]
            distance = row[1] if len(row) > 1 else None
            self._attach_similarity(product, distance)
            products.append(product)
        
        return products

    async def search_keyword(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 10, 
        filter_gender: Optional[str] = None
    ) -> List[Product]:
        
        search_pattern = f"%{query}%"
        conditions = [
            Product.is_active == True, 
            Product.deleted_at.is_(None), 
            or_(
                Product.name.ilike(search_pattern), 
                Product.description.ilike(search_pattern), 
                Product.category.ilike(search_pattern)
            )
        ]
        
        if filter_gender: 
            conditions.append(or_(Product.gender == filter_gender, Product.gender == 'Unisex', Product.gender.is_(None)))
        
        stmt = select(Product).where(*conditions).order_by(Product.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        products = list(result.scalars().all())
        
        # 키워드 검색은 similarity 없음
        for p in products:
            p.similarity = None
        
        return products

crud_product = CRUDProduct()