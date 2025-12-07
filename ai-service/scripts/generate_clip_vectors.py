#!/usr/bin/env python3
"""
generate_clip_vectors.py
AI 서비스 컨테이너 내에서 실행하여 모든 상품에 CLIP 벡터 생성

사용법:
1. 이 파일을 ai-service/scripts/ 에 복사
2. docker exec -it ai-service-api python /app/scripts/generate_clip_vectors.py

또는 docker-compose로:
docker compose -f docker-compose.dev.yml exec ai-service-api python /app/scripts/generate_clip_vectors.py
"""

import os
import sys
import asyncio
import logging
import base64
from io import BytesIO

import httpx
import asyncpg
from PIL import Image

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 환경변수에서 DB 설정 읽기
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://modify_user:modify_password@postgres:5432/modify_db")

# sentence-transformers 로드
try:
    from sentence_transformers import SentenceTransformer
    CLIP_MODEL = SentenceTransformer("sentence-transformers/clip-ViT-B-32", device="cpu")
    logger.info("✅ CLIP Vision model loaded")
except Exception as e:
    logger.error(f"❌ Failed to load CLIP model: {e}")
    sys.exit(1)


async def get_products_without_clip(conn) -> list:
    """CLIP 벡터가 없는 상품 조회"""
    rows = await conn.fetch("""
        SELECT id, name, image_url 
        FROM products 
        WHERE embedding_clip IS NULL 
          AND image_url IS NOT NULL 
          AND image_url != ''
          AND deleted_at IS NULL
        ORDER BY id
    """)
    return [dict(row) for row in rows]


async def download_image(url: str) -> Image.Image:
    """이미지 다운로드"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                return img
    except Exception as e:
        logger.debug(f"Download failed: {url} - {e}")
    return None


def generate_clip_vector(image: Image.Image) -> list:
    """CLIP Vision으로 이미지 벡터 생성"""
    try:
        # 이미지 리사이즈 (CLIP 입력 크기)
        image = image.resize((224, 224))
        vector = CLIP_MODEL.encode(image)
        return vector.tolist()
    except Exception as e:
        logger.error(f"CLIP encoding failed: {e}")
        return None


async def update_clip_vector(conn, product_id: int, vector: list) -> bool:
    """DB에 CLIP 벡터 저장"""
    try:
        # pgvector 형식으로 변환
        vector_str = "[" + ",".join(map(str, vector)) + "]"
        await conn.execute("""
            UPDATE products 
            SET embedding_clip = $1::vector
            WHERE id = $2
        """, vector_str, product_id)
        return True
    except Exception as e:
        logger.error(f"DB update failed for product {product_id}: {e}")
        return False


async def process_product(conn, product: dict) -> bool:
    """단일 상품 처리"""
    product_id = product["id"]
    name = product["name"]
    image_url = product["image_url"]
    
    # 1. 이미지 다운로드
    image = await download_image(image_url)
    if not image:
        logger.warning(f"⚠️ [{product_id}] {name}: 이미지 다운로드 실패")
        return False
    
    # 2. CLIP 벡터 생성
    vector = generate_clip_vector(image)
    if not vector:
        logger.warning(f"⚠️ [{product_id}] {name}: CLIP 벡터 생성 실패")
        return False
    
    # 3. DB 저장
    success = await update_clip_vector(conn, product_id, vector)
    if success:
        logger.info(f"✅ [{product_id}] {name}: CLIP 벡터 저장 완료 ({len(vector)}차원)")
        return True
    
    return False


async def main():
    logger.info("=" * 60)
    logger.info("🚀 CLIP 이미지 벡터 일괄 생성 시작")
    logger.info("=" * 60)
    
    # DB 연결
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return
    
    try:
        # CLIP 벡터 없는 상품 조회
        products = await get_products_without_clip(conn)
        total = len(products)
        
        if total == 0:
            logger.info("✨ 모든 상품에 CLIP 벡터가 이미 있습니다!")
            return
        
        logger.info(f"📦 처리할 상품: {total}개")
        logger.info("-" * 60)
        
        success = 0
        failed = 0
        
        for i, product in enumerate(products, 1):
            logger.info(f"[{i}/{total}] 처리 중...")
            
            if await process_product(conn, product):
                success += 1
            else:
                failed += 1
            
            # 매 10개마다 잠시 대기 (서버 부하 방지)
            if i % 10 == 0:
                await asyncio.sleep(1)
        
        logger.info("=" * 60)
        logger.info("🎉 CLIP 벡터 생성 완료!")
        logger.info(f"   ✅ 성공: {success}개")
        logger.info(f"   ❌ 실패: {failed}개")
        logger.info(f"   📊 전체: {total}개")
        logger.info("=" * 60)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())