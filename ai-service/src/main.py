import logging
import json
import re
import base64
from fastapi import FastAPI, HTTPException, APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict
from contextlib import asynccontextmanager

from src.core.model_engine import model_engine
from src.core.prompts import VISION_ANALYSIS_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class EmbedResponse(BaseModel):
    vector: List[float]

class ImageAnalysisResponse(BaseModel):
    name: str
    category: str
    gender: str
    description: str
    price: int
    vector: List[float]

class PathRequest(BaseModel):
    query: str

class InternalSearchRequest(BaseModel):
    query: str
    image_b64: Optional[str] = None

class SearchProcessResponse(BaseModel):
    vector: List[float]
    reason: str

# --- Helper Methods ---

def _fix_encoding(text: str) -> str:
    """
    [핵심] 깨진 한글(Mojibake) 및 유니코드 이스케이프 완벽 복구
    Case 1: "í¬ë¦¬..." (UTF-8 bytes read as Latin-1) -> "크리..."
    Case 2: "\ud558..." (Unicode Escape) -> "하..."
    """
    if not text:
        return ""

    # 1. Mojibake 복구 시도 (Latin-1 -> UTF-8)
    try:
        # 깨진 문자열을 다시 바이트로 돌리고(latin1), UTF-8로 다시 읽음
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
            return _fix_encoding(clean_val) # 추출한 값도 인코딩 보정
    return default

# --- Endpoints ---

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
        
        prompt = VISION_ANALYSIS_PROMPT
        
        logger.info(f"👁️ Analyzing image: {filename}...")
        generated_text = model_engine.generate_with_image(prompt, image_b64)
        
        # [Critical] 1차 인코딩 보정 (전체 텍스트 복구)
        generated_text = _fix_encoding(generated_text)
        logger.info(f"🤖 Raw AI Response: {generated_text}")

        # [Safety Check]
        if "cannot assist" in generated_text or "I cannot" in generated_text:
            raise ValueError("AI Safety Filter Triggered")

        # [Parsing Logic]
        product_data = {}
        parsing_success = False

        # 전략 1: JSON 파싱
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

        # 전략 2: Fallback Parser
        if not parsing_success:
            logger.info("🔧 Running Fallback Parser...")
            
            product_data["name"] = _extract_from_text(
                generated_text, 
                [r'"?name"?\s*:\s*"([^"]+)"', r'"?이름"?\s*:\s*"([^"]+)"', r'Name:\s*(.+)']
            )
            product_data["category"] = _extract_from_text(
                generated_text, 
                [r'"?category"?\s*:\s*"([^"]+)"', r'"?카테고리"?\s*:\s*"([^"]+)"', r'Category:\s*(.+)'
                ], "Uncategorized"
            )
            product_data["gender"] = _extract_from_text(
                generated_text,
                [r'"?gender"?\s*:\s*"([^"]+)"', r'"?성별"?\s*:\s*"([^"]+)"', r'Gender:\s*(.+)'],
                "Unisex"
            )
            product_data["description"] = _extract_from_text(
                generated_text,
                [r'"?description"?\s*:\s*"([^"]+)"', r'"?설명"?\s*:\s*"([^"]+)"', r'Description:\s*(.+)'],
                "AI 상세 분석 내용입니다."
            )
            
            price_str = _extract_from_text(
                generated_text,
                [r'"?price"?\s*:\s*([\d,]+)', r'"?가격"?\s*:\s*([\d,]+)', r'Price:\s*([\d,]+)'],
                "0"
            )
            try:
                product_data["price"] = int(re.sub(r"[^0-9]", "", price_str))
            except:
                product_data["price"] = 0

        # [Normalization & 2차 인코딩 보정]
        # JSON으로 파싱되었더라도 값 내부가 깨져있을 수 있으므로 한번 더 체크
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

        # 벡터 생성
        meta_text = f"[{final_gender}] {final_name} {final_cat} {final_desc}"
        vector = model_engine.generate_embedding(meta_text)

        logger.info(f"✅ Analysis Success: {final_name} ({final_gender}) - {price}원")

        return {
            "name": final_name,
            "category": final_cat,
            "gender": final_gender,
            "description": final_desc,
            "price": price,
            "vector": vector
        }

    except Exception as e:
        logger.error(f"❌ Analysis Critical Error: {e}")
        return {
            "name": f"등록된 상품 ({filename})",
            "category": "Etc",
            "gender": "Unisex",
            "description": "이미지 분석 실패.",
            "price": 0,
            "vector": [0.0] * 768
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

@api_router.post("/determine-path")
async def determine_path(request: PathRequest):
    return {"path": "INTERNAL"}

@api_router.post("/process-internal", response_model=SearchProcessResponse)
async def process_internal(request: InternalSearchRequest):
    query = request.query
    vector = model_engine.generate_embedding(query)
    return {"vector": vector, "reason": f"'{query}' 검색 결과입니다."}

@api_router.post("/process-external", response_model=SearchProcessResponse)
async def process_external(request: InternalSearchRequest):
    return await process_internal(request)

app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Modify AI Service is Running"}