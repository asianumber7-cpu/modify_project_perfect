import logging
import json
from fastapi import FastAPI, HTTPException, APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# model_engine (이전과 동일)
from src.core.model_engine import model_engine

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- [LifeSpan] ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Initializing AI Models...")
    try:
        model_engine.initialize()
    except Exception as e:
        logger.error(f"⚠️ Model init deferred: {e}")
    yield
    logger.info("💤 Shutting down...")

app = FastAPI(title="Modify AI Service", version="1.0.0", lifespan=lifespan)
api_router = APIRouter(prefix="/api/v1")

# --- [DTO 정의] ---
class EmbedRequest(BaseModel):
    text: str

class EmbedResponse(BaseModel):
    vector: List[float]

class ImageAnalysisResponse(BaseModel):
    name: str
    category: str
    description: str
    price: int
    vector: List[float]

# 🚨 [NEW] 검색용 DTO 추가
class PathRequest(BaseModel):
    query: str

class InternalSearchRequest(BaseModel):
    query: str
    image_b64: Optional[str] = None  # 이미지가 있을 경우 Base64로 받음

class SearchProcessResponse(BaseModel):
    vector: List[float]
    reason: str

# --- [Existing Endpoints] ---

@api_router.post("/embed-text", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """단순 텍스트 임베딩 (상품 등록 시 사용)"""
    try:
        vector = model_engine.generate_embedding(request.text)
        return {"vector": vector}
    except Exception as e:
        logger.error(f"Embedding Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    """이미지 분석 및 JSON 생성 (상품 등록 시 사용)"""
    try:
        filename = file.filename
        prompt = f"""
        You are a professional fashion MD.
        Based on the image filename '{filename}', predict the product details.
        RULE: Return ONLY a JSON object with keys: "name", "category", "description", "price".
        """
        generated_text = model_engine.generate_text(prompt)
        
        try:
            cleaned_text = generated_text.replace("```json", "").replace("```", "").strip()
            product_data = json.loads(cleaned_text)
        except Exception:
            product_data = {
                "name": f"AI 분석 상품 ({filename})", 
                "category": "Uncategorized", 
                "description": "AI 분석 실패", 
                "price": 0
            }

        meta_text = f"{product_data.get('name')} {product_data.get('category')} {product_data.get('description')}"
        vector = model_engine.generate_embedding(meta_text)

        return {
            "name": product_data.get("name"),
            "category": product_data.get("category"),
            "description": product_data.get("description"),
            "price": int(product_data.get("price", 0)),
            "vector": vector
        }
    except Exception as e:
        logger.error(f"Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [NEW Endpoints for Search] ---
# Backend의 search.py가 호출하는 엔드포인트들입니다.

@api_router.post("/determine-path")
async def determine_path(request: PathRequest):
    """
    검색어의 의도를 파악하여 INTERNAL(내부 DB) 또는 EXTERNAL(외부 검색) 경로를 결정합니다.
    """
    try:
        # LLM에게 판단을 맡기거나, 간단한 규칙 기반으로 처리
        # 쇼핑몰 검색이므로 기본값은 INTERNAL
        path = "INTERNAL"
        
        # (선택사항) LLM을 사용하여 의도 파악
        # intent_prompt = f"Is the query '{request.query}' asking for general news/trends (EXTERNAL) or searching for a product to buy (INTERNAL)? Reply only INTERNAL or EXTERNAL."
        # path = model_engine.generate_text(intent_prompt).strip()
        
        return {"path": path}
    except Exception as e:
        logger.error(f"Path determination failed: {e}")
        return {"path": "INTERNAL"} # 에러 시 안전하게 내부 검색으로 처리

@api_router.post("/process-internal", response_model=SearchProcessResponse)
async def process_internal(request: InternalSearchRequest):
    """
    내부 DB 검색을 위한 벡터와 AI 추천 멘트를 생성합니다.
    """
    try:
        query = request.query
        
        # 1. 검색 쿼리 벡터화 (가장 중요)
        vector = model_engine.generate_embedding(query)
        
        # 2. AI 추천 멘트 생성 (Watsonx 활용)
        prompt = f"""
        사용자가 쇼핑몰에서 '{query}'를 검색했습니다. 
        이 고객에게 보여줄 매력적인 상품 추천 멘트를 한국어로 한 문장만 작성해주세요.
        예시: "{query}와 관련된 트렌디한 상품들을 모아봤습니다."
        """
        try:
            reason = model_engine.generate_text(prompt).strip()
        except Exception:
            reason = f"'{query}'에 대한 AI 추천 결과입니다."
            
        return {"vector": vector, "reason": reason}

    except Exception as e:
        logger.error(f"Internal Search Process Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/process-external", response_model=SearchProcessResponse)
async def process_external(request: InternalSearchRequest):
    """
    외부 검색 처리 (현재는 내부 검색과 동일하게 처리하거나 더미 데이터 반환)
    """
    # 현재 외부 검색 로직이 없으므로 내부 검색 로직 재사용
    return await process_internal(request)


# Router 등록
app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Modify AI Service is Running"}