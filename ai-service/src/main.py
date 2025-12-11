import logging
import json
import re
import base64
import os
import uuid
import traceback
from fastapi import FastAPI, HTTPException, APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from src.core.model_engine import model_engine
from src.core.prompts import VISION_ANALYSIS_PROMPT
from src.services.rag_orchestrator import rag_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI Service Starting...")
    try:
        model_engine.initialize()
    except Exception as e:
        logger.error(f"⚠️ Model init warning: {e}")
    yield
    logger.info("💤 AI Service Shutting down...")

app = FastAPI(title="Modify AI Service", version="1.0.0", lifespan=lifespan)
api_router = APIRouter(prefix="/api/v1")

# --- DTO ---
class EmbedRequest(BaseModel):
    text: str

class AnalyzeRequest(BaseModel):
    image_b64: str
    query: str   

class EmbedResponse(BaseModel):
    vector: List[float]

class ImageAnalysisResponse(BaseModel):
    name: str
    category: str
    gender: str
    description: str
    price: int
    vector: List[float]           # BERT (768)
    vector_clip: List[float]      # CLIP Full (512)
    vector_clip_upper: List[float] # CLIP Upper (512)
    vector_clip_lower: List[float] # CLIP Lower (512)
class PathRequest(BaseModel):
    query: str

class InternalSearchRequest(BaseModel):
    query: str
    image_b64: Optional[str] = None

# CLIP 벡터 생성 요청
class ClipVectorRequest(BaseModel):
    image_b64: str

class ClipVectorResponse(BaseModel):
    vector: List[float]
    dimension: int

# 이미지 기반 상품 검색 요청
class ImageSearchRequest(BaseModel):
    image_b64: str
    limit: int = 12

# --- Helper Methods (기존 코드 유지) ---

def _fix_encoding(text: str) -> str:
    """
    [핵심] 깨진 한글(Mojibake) 및 유니코드 이스케이프 완벽 복구
    """
    if not text:
        return ""

    # 1. Mojibake 복구 시도 (Latin-1 -> UTF-8)
    try:
        fixed = text.encode('latin1').decode('utf-8')
        return fixed
    except Exception:
        pass

    # 2. 유니코드 이스케이프 복구 시도
    try:
        return text.encode('utf-8').decode('unicode_escape')
    except Exception:
        pass
        
    return text

def _extract_from_text(text: str, key_patterns: List[str], default: str = "") -> str:
    """JSON 파싱 실패 시 정규식 추출 + 인코딩 자동 보정"""
    for pattern in key_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            clean_val = match.group(1).strip().strip('",').strip()
            return _fix_encoding(clean_val)
    return default

CATEGORY_MAP = {
    # AI가 뱉을 수 있는 한글 -> DB에 저장할 영어 표준
    "상의": "Tops",
    "티셔츠": "Tops",
    "니트": "Tops",
    "셔츠": "Tops",
    
    "하의": "Bottoms",
    "바지": "Bottoms",
    "치마": "Bottoms",
    "스커트": "Bottoms",
    "팬츠": "Bottoms",
    "진": "Bottoms",
    
    "아우터": "Outerwear",
    "자켓": "Outerwear",
    "코트": "Outerwear",
    "패딩": "Outerwear",
    
    "원피스": "Dresses",
    "드레스": "Dresses",
    
    "신발": "Shoes",
    "슈즈": "Shoes",
    
    "액세서리": "Accessories",
    "모자": "Accessories",
    "가방": "Accessories"
}

# --- Endpoints (기존 기능 유지) ---

@api_router.post("/embed-text", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    try:
        vector = model_engine.generate_embedding(request.text)
        return {"vector": vector}
    except:
        return {"vector": [0.0] * 768} 

@api_router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    filename = file.filename
    try:
        contents = await file.read()
        image_b64 = base64.b64encode(contents).decode("utf-8")
        
        logger.info(f"👁️ Analyzing image: {filename}...")
        
        # 1. Text Generation (Llama)
        generated_text = model_engine.generate_with_image(VISION_ANALYSIS_PROMPT, image_b64)
        
        # JSON Parsing (이미 model_engine 내부에서 인코딩/파싱 처리됨)
        try:
            product_data = json.loads(generated_text)
        except:
            product_data = {
                "name": f"상품 {filename}", 
                "category": "Fashion", 
                "price": 0, 
                "gender": "Unisex", 
                "description": generated_text[:200]
            }

        # ---------------------------------------------------------
        # 한글 카테고리를 영어 표준(Enum)으로 변환
        # ---------------------------------------------------------
        raw_category = product_data.get("category", "Etc") # AI가 준 값 (예: "아우터")
        
        # 1. 매핑 테이블에서 찾기
        standard_category = CATEGORY_MAP.get(raw_category)
        
        # 2. 못 찾았다면, 혹시 키워드가 포함되어 있는지 확인 (유연성 확보)
        if not standard_category:
            for kr_key, en_val in CATEGORY_MAP.items():
                if kr_key in raw_category: # 예: "멋진 아우터" -> "Outerwear"
                    standard_category = en_val
                    break
        
        # 3. 그래도 없으면 기본값 혹은 원본 사용 (단, 원본이 영어일 수도 있으니)
        final_category = standard_category if standard_category else "Etc"
        
        # 변환된 카테고리를 덮어씌움
        product_data["category"] = final_category
        
        logger.info(f"🔄 Category Mapped: '{raw_category}' -> '{final_category}'")
        # ---------------------------------------------------------    

        # 2. Vector Generation (BERT + CLIP Full/Upper/Lower)
        # BERT (768)
        meta_text = f"[{product_data.get('gender')}] {product_data.get('name')} {product_data.get('category')}"
        vector_bert = model_engine.generate_embedding(meta_text)
        
        # CLIP (512 x 3) - Optimized & Zero-padded safe
        fashion_vectors = model_engine.generate_fashion_embeddings(image_b64)
        
        logger.info(f"✅ Analysis Success: {product_data.get('name')}")
        
        return {
            "name": product_data.get("name", "Unknown"),
            "category": product_data.get("category", "Etc"),
            "gender": product_data.get("gender", "Unisex"),
            "description": product_data.get("description", ""),
            "price": product_data.get("price", 0),
            "vector": vector_bert,
            "vector_clip": fashion_vectors["full"],
            "vector_clip_upper": fashion_vectors["upper"],
            "vector_clip_lower": fashion_vectors["lower"]
        }

    except Exception as e:
        logger.error(f"❌ Analysis Critical Error: {e}")
        # Error Fallback (DB Insert를 위해 모든 벡터 0 채움)
        zero_512 = [0.0] * 512
        return {
            "name": f"ErrorItem ({filename})",
            "category": "Error",
            "gender": "Unisex",
            "description": "분석 실패",
            "price": 0,
            "vector": [0.0] * 768,
            "vector_clip": zero_512,
            "vector_clip_upper": zero_512,
            "vector_clip_lower": zero_512
        }

@api_router.post("/llm-generate-response")
async def llm_generate(body: Dict[str, str]):
    prompt = body.get("prompt", "")
    logger.info(f"📝 LLM Prompt received: {prompt[:100]}...")
    try:
        korean_prompt = f"질문: {prompt}\n답변 (한국어):"
        answer = model_engine.generate_text(korean_prompt)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"❌ LLM Generation Failed: {e}")
        logger.error(traceback.format_exc())
        return {"answer": "죄송합니다. AI 응답을 생성할 수 없습니다."}
    
@api_router.post("/analyze-image-detail")
async def analyze_image_detail(req: AnalyzeRequest):
    """특정 이미지에 대한 상세 분석 요청 (RAG용 - base64 이미지)"""
    result = await rag_orchestrator.analyze_specific_image(req.image_b64, req.query)
    return {"analysis": result}    


# -------------------------------------------------------------
# CLIP 이미지 벡터 생성 엔드포인트
# -------------------------------------------------------------

@api_router.post("/generate-clip-vector", response_model=ClipVectorResponse)
async def generate_clip_vector(request: ClipVectorRequest):
    """
    이미지에서 CLIP 벡터(512차원) 생성
    - 후보 이미지 클릭 시 상품 재검색에 사용
    - 상품 등록 시 CLIP 벡터 저장에 사용
    """
    try:
        image_b64 = request.image_b64
        
        # data:image/... 형식이면 base64 부분만 추출
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]
        
        # CLIP Vision 모델로 벡터 생성 (YOLO 적용)
        result = model_engine.generate_image_embedding(image_b64, use_yolo=True)
        clip_vector = result.get("clip", [])
        
        if not clip_vector or len(clip_vector) == 0:
            raise HTTPException(status_code=500, detail="CLIP 벡터 생성 실패")
        
        logger.info(f"✅ CLIP vector generated: {len(clip_vector)} dimensions")
        
        return {
            "vector": clip_vector,
            "dimension": len(clip_vector)
        }
        
    except Exception as e:
        logger.error(f"❌ CLIP vector generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ NEW: 패션 특화 CLIP 벡터 생성 (YOLO + 상의/하의 분리)
class FashionClipRequest(BaseModel):
    image_b64: str
    target: str = "full"  # "full", "upper", "lower"


@api_router.post("/generate-fashion-clip-vector")
async def generate_fashion_clip_vector(request: FashionClipRequest):
    """
    ✅ 패션 특화 CLIP 벡터 생성
    - YOLO로 사람/옷 영역 감지 후 크롭
    - target: "full"(전신), "upper"(상의), "lower"(하의)
    """
    try:
        image_b64 = request.image_b64
        target = request.target
        
        # data:image/... 형식이면 base64 부분만 추출
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]
        
        # PIL Image로 변환
        import io
        from PIL import Image
        pil_image = Image.open(io.BytesIO(base64.b64decode(image_b64)))
        
        # YOLO로 영역 크롭 후 CLIP 벡터 생성
        try:
            from src.core.yolo_detector import yolo_detector
            
            # YOLO 초기화
            if not yolo_detector.initialized:
                yolo_detector.initialize()
            
            # 지정된 영역 크롭
            cropped = yolo_detector.crop_fashion_regions(pil_image, target=target)
            
            if cropped is not None:
                logger.info(f"✂️ YOLO cropped '{target}' region: {cropped.size}")
                pil_image = cropped

                # ✅ [DEBUG] 크롭된 이미지가 맞는지 눈으로 확인하기 위해 저장!
                debug_dir = "/app/static/debug" # 도커 볼륨 경로 확인 필요 (혹은 "./debug_images")
                os.makedirs(debug_dir, exist_ok=True)
                debug_filename = f"{debug_dir}/{uuid.uuid4()}_{target}.jpg"
                pil_image.save(debug_filename)
                logger.info(f"📸 Debug Image Saved: {debug_filename}")


            else:
                logger.warning(f"⚠️ YOLO crop failed for '{target}', using original")
                
        except ImportError as e:
            logger.warning(f"⚠️ YOLO not available: {e}")
        except Exception as e:
            logger.warning(f"⚠️ YOLO failed: {e}")
        
        # CLIP 벡터 생성 (YOLO 중복 적용 방지)
        result = model_engine.generate_image_embedding(pil_image, use_yolo=False)
        clip_vector = result.get("clip", [])
        
        if not clip_vector or len(clip_vector) == 0:
            raise HTTPException(status_code=500, detail="CLIP 벡터 생성 실패")
        
        logger.info(f"✅ Fashion CLIP vector generated ({target}): {len(clip_vector)} dimensions")
        
        return {
            "vector": clip_vector,
            "dimension": len(clip_vector),
            "target": target
        }
        
    except Exception as e:
        logger.error(f"❌ Fashion CLIP vector generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/search-by-image")
async def search_by_image(request: ImageSearchRequest):
    """
    이미지 기반 상품 검색
    - 후보 이미지 클릭 시 호출
    - 이미지 → CLIP 벡터 → 유사 상품 검색
    """
    try:
        image_b64 = request.image_b64
        
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]
        
        # CLIP 벡터 생성
        result = model_engine.generate_image_embedding(image_b64)
        clip_vector = result.get("clip", [])
        
        if not clip_vector:
            raise HTTPException(status_code=500, detail="CLIP 벡터 생성 실패")
        
        logger.info(f"🖼️ Image search: CLIP vector generated ({len(clip_vector)} dims)")
        
        return {
            "vectors": {
                "clip": clip_vector,
                "bert": None
            },
            "search_type": "image_similarity"
        }
        
    except Exception as e:
        logger.error(f"❌ Image search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------------
#  RAG Orchestrator 연결 (검색 로직 고도화)
# -------------------------------------------------------------

@api_router.post("/determine-path")
async def determine_path(request: PathRequest):
    """
    사용자 쿼리를 분석하여 검색 경로(INTERNAL vs EXTERNAL)를 결정합니다.
    """
    logger.info(f"🤔 Determining path for query: {request.query}")
    try:
        decision = await rag_orchestrator.determine_search_path(request.query)
        logger.info(f"👉 Decision: {decision}")
        return {"path": decision}
    except Exception as e:
        logger.error(f"Determine path error: {e}")
        return {"path": "INTERNAL"}

@api_router.post("/process-internal")
async def process_internal(request: InternalSearchRequest):
    """
    내부 검색 로직 실행
    """
    logger.info(f"🏢 Processing Internal (Orchestrator): {request.query}")
    return await rag_orchestrator.process_internal_search(request.query)

@api_router.post("/process-external")
async def process_external(request: InternalSearchRequest):
    """
    외부(Google+RAG) 검색 로직 실행
    """
    logger.info(f"🌍 Processing External (Orchestrator): {request.query}")
    try:
        result = await rag_orchestrator.process_external_rag(request.query)
        return result
    except Exception as e:
        logger.error(f"External processing failed: {e}")
        return await rag_orchestrator.process_internal_search(request.query)

app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Modify AI Service is Running"}