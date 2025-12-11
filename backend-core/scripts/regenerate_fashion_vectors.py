"""
regenerate_fashion_vectors.py
경로: backend-core/scripts/regenerate_fashion_vectors.py

기존 상품의 embedding_clip_upper, embedding_clip_lower 벡터 생성
실행: docker exec -it modify-backend python scripts/regenerate_fashion_vectors.py
"""

import asyncio
import httpx
import base64
import logging
import asyncpg

# 설정
DATABASE_URL = "postgresql://modify_user:modify_password@postgres:5432/modify_db"
AI_SERVICE_URL = "http://ai-service-api:8000/api/v1"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def regenerate_vectors():
    """모든 상품의 upper/lower 벡터 재생성"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # 1. embedding_clip_upper가 NULL인 상품 조회
        products = await conn.fetch("""
            SELECT id, name, image_url 
            FROM products 
            WHERE embedding_clip_upper IS NULL 
            AND image_url IS NOT NULL 
            AND image_url NOT LIKE '%placehold%'
            AND deleted_at IS NULL
            ORDER BY id
        """)
        
        logger.info(f"📦 Found {len(products)} products to process")
        
        success_count = 0
        fail_count = 0
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for product in products:
                product_id = product['id']
                product_name = product['name']
                image_url = product['image_url']
                
                logger.info(f"🔄 Processing [{product_id}] {product_name[:30]}...")
                
                try:
                    # 이미지 다운로드
                    img_res = await client.get(image_url)
                    if img_res.status_code != 200:
                        logger.warning(f"  ⚠️ Image download failed: {image_url[:50]}...")
                        fail_count += 1
                        continue
                    
                    image_b64 = base64.b64encode(img_res.content).decode("utf-8")
                    
                    # Full 벡터
                    full_res = await client.post(
                        f"{AI_SERVICE_URL}/generate-fashion-clip-vector",
                        json={"image_b64": image_b64, "target": "full"}
                    )
                    vector_full = full_res.json().get("vector", []) if full_res.status_code == 200 else None
                    
                    # Upper 벡터
                    upper_res = await client.post(
                        f"{AI_SERVICE_URL}/generate-fashion-clip-vector",
                        json={"image_b64": image_b64, "target": "upper"}
                    )
                    vector_upper = upper_res.json().get("vector", []) if upper_res.status_code == 200 else None
                    
                    # Lower 벡터
                    lower_res = await client.post(
                        f"{AI_SERVICE_URL}/generate-fashion-clip-vector",
                        json={"image_b64": image_b64, "target": "lower"}
                    )
                    vector_lower = lower_res.json().get("vector", []) if lower_res.status_code == 200 else None
                    
                    # DB 업데이트
                    await conn.execute("""
                        UPDATE products 
                        SET embedding_clip = $1,
                            embedding_clip_upper = $2,
                            embedding_clip_lower = $3,
                            updated_at = NOW()
                        WHERE id = $4
                    """, 
                        str(vector_full) if vector_full else None,
                        str(vector_upper) if vector_upper else None,
                        str(vector_lower) if vector_lower else None,
                        product_id
                    )
                    
                    logger.info(f"  ✅ Updated - Full: {len(vector_full) if vector_full else 0}, Upper: {len(vector_upper) if vector_upper else 0}, Lower: {len(vector_lower) if vector_lower else 0}")
                    success_count += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"  ❌ Error: {e}")
                    fail_count += 1
                    continue
        
        logger.info("=" * 50)
        logger.info(f"🎉 Completed! Success: {success_count}, Failed: {fail_count}")
        logger.info("=" * 50)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(regenerate_vectors())