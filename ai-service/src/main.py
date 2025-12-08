import logging
import json
import re
import base64
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
    vector: List[float]           # BERT 벡터 (768차원)
    vector_clip: List[float]      # CLIP 벡터 (512차원) - 신규 추가

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
    """
    이미지 분석 및 상품 정보 생성
    - BERT 벡터 (768차원): 텍스트 기반 검색용
    - CLIP 벡터 (512차원): 이미지 기반 시각적 유사도 검색용
    """
    filename = file.filename
    try:
        contents = await file.read()
        image_b64 = base64.b64encode(contents).decode("utf-8")
        
        prompt = VISION_ANALYSIS_PROMPT
        
        logger.info(f"👁️ Analyzing image: {filename}...")
        generated_text = model_engine.generate_with_image(prompt, image_b64)
        
        # [Critical] 1차 인코딩 보정
        generated_text = _fix_encoding(generated_text)
        logger.info(f"🤖 Raw AI Response: {generated_text}")

        if "cannot assist" in generated_text or "I cannot" in generated_text:
            raise ValueError("AI Safety Filter Triggered")

        product_data = {}
        parsing_success = False

        # JSON 파싱 시도
        try:
            json_match = re.search(r"\{[\s\S]*\}", generated_text)
            if json_match:
                clean_json = json_match.group()
                clean_json = re.sub(r"```json|```", "", clean_json)
                product_data = json.loads(clean_json)
                parsing_success = True
            else:
                product_data = json.loads(generated_text)
                parsing_success = True
        except Exception as e:
            logger.warning(f"⚠️ JSON Parsing failed: {e}. Attempting Fallback Regex...")

        # Fallback Parser
        if not parsing_success:
            logger.info("🔧 Running Fallback Parser...")
            product_data["name"] = _extract_from_text(generated_text, [r'"?name"?\s*:\s*"([^"]+)"', r'"?이름"?\s*:\s*"([^"]+)"', r'Name:\s*(.+)'])
            product_data["category"] = _extract_from_text(generated_text, [r'"?category"?\s*:\s*"([^"]+)"', r'"?카테고리"?\s*:\s*"([^"]+)"', r'Category:\s*(.+)'], "Uncategorized")
            product_data["gender"] = _extract_from_text(generated_text, [r'"?gender"?\s*:\s*"([^"]+)"', r'"?성별"?\s*:\s*"([^"]+)"', r'Gender:\s*(.+)'], "Unisex")
            product_data["description"] = _extract_from_text(generated_text, [r'"?description"?\s*:\s*"([^"]+)"', r'"?설명"?\s*:\s*"([^"]+)"', r'Description:\s*(.+)'], "AI 상세 분석 내용입니다.")
            price_str = _extract_from_text(generated_text, [r'"?price"?\s*:\s*([\d,]+)', r'"?가격"?\s*:\s*([\d,]+)', r'Price:\s*([\d,]+)'], "0")
            try:
                product_data["price"] = int(re.sub(r"[^0-9]", "", price_str))
            except:
                product_data["price"] = 0

        # 데이터 정규화 및 벡터 생성
        final_name = _fix_encoding(product_data.get("name"))
        if not final_name or "상품명" in final_name or "JSON" in final_name:
             final_name = f"AI 추천 상품 ({filename.split('.')[0]})"
        
        final_desc = _fix_encoding(product_data.get("description"))
        if not final_desc or len(final_desc) < 5:
            final_desc = "AI가 이미지를 분석하여 추천하는 상품입니다."

        final_cat = _fix_encoding(product_data.get("category", "Uncategorized"))
        
        raw_gender = str(product_data.get("gender", "Unisex"))
        if any(x in raw_gender.lower() for x in ['wo', 'female', 'girl', 'lady', '여성', '여자']):
            final_gender = 'Female'
        elif any(x in raw_gender.lower() for x in ['man', 'male', 'boy', '남성', '남자']):
            final_gender = 'Male'
        else:
            final_gender = 'Unisex'

        try:
            raw_price = str(product_data.get("price", 0))
            price = int(re.sub(r"[^0-9]", "", raw_price))
        except:
            price = 0

        # ============================================================
        # [BERT 벡터] 텍스트 기반 임베딩 (768차원)
        # ============================================================
        meta_text = f"[{final_gender}] {final_name} {final_cat} {final_desc}"
        vector = model_engine.generate_embedding(meta_text)

        # ============================================================
        # [CLIP 벡터] 이미지 기반 시각적 임베딩 (512차원) - 신규 추가!
        # ============================================================
        vector_clip = []
        try:
            clip_result = model_engine.generate_image_embedding(image_b64)
            vector_clip = clip_result.get("clip", [])
            if vector_clip:
                logger.info(f"🖼️ CLIP vector generated: {len(vector_clip)} dimensions")
            else:
                logger.warning("⚠️ CLIP vector empty, using zeros")
                vector_clip = [0.0] * 512
        except Exception as e:
            logger.error(f"❌ CLIP vector generation failed: {e}")
            vector_clip = [0.0] * 512

        logger.info(f"✅ Analysis Success: {final_name} ({final_gender}) - {price}원")
        logger.info(f"   📊 BERT: {len(vector)}dim, CLIP: {len(vector_clip)}dim")

        return {
            "name": final_name,
            "category": final_cat,
            "gender": final_gender,
            "description": final_desc,
            "price": price,
            "vector": vector,           # BERT 768차원
            "vector_clip": vector_clip  # CLIP 512차원
        }

    except Exception as e:
        logger.error(f"❌ Analysis Critical Error: {e}")
        return {
            "name": f"등록된 상품 ({filename})",
            "category": "Etc",
            "gender": "Unisex",
            "description": "이미지 분석 실패.",
            "price": 0,
            "vector": [0.0] * 768,
            "vector_clip": [0.0] * 512
        }

@api_router.post("/llm-generate-response")
async def llm_generate(body: Dict[str, str]):
    prompt = body.get("prompt", "")
    try:
        korean_prompt = f"질문: {prompt}\n답변 (한국어):"
        answer = model_engine.generate_text(korean_prompt)
        return {"answer": answer}
    except:
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