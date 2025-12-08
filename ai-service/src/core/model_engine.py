import os
import logging
import base64
import io
import threading
from typing import List, Optional, Dict, Union
from PIL import Image

# [AI Core]
import torch
from sentence_transformers import SentenceTransformer, util 
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ibm import ChatWatsonx
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# [상수 정의]
BERT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
CLIP_MODEL_NAME = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
CLIP_VISION_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
VISION_MODEL_ID = "meta-llama/llama-3-2-11b-vision-instruct" 

class ModelEngine:
    """
    4-Model Hybrid Engine Singleton Class
    - Watsonx (VLM): Image Analysis (Writer)
    - BERT: Text Embedding (Retriever)
    - CLIP Text: Query to Vector (Scorer-Criteria)
    - CLIP Vision: Image to Vector (Scorer-Candidate)
    """
    _instance: Optional['ModelEngine'] = None
    _lock = threading.Lock() # Thread-safe initialization
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 이미 초기화되었다면 건너뜀 (Singleton 보장)
        if hasattr(self, 'is_initialized') and self.is_initialized:
            return
            
        self.vision_model: Optional[ChatWatsonx] = None
        self.text_model: Optional[ChatWatsonx] = None
        self.bert_model: Optional[HuggingFaceEmbeddings] = None
        self.clip_text_model: Optional[SentenceTransformer] = None
        self.clip_vision_model: Optional[SentenceTransformer] = None
        
        self.project_id = os.getenv("WATSONX_PROJECT_ID")
        self.device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self.is_initialized = False

    def initialize(self):
        """Lazy Loading Pattern: 첫 요청 시 모델 로드"""
        if self.is_initialized: return
        
        with self._lock:
            if self.is_initialized: return
            logger.info(f"🚀 Initializing Hybrid Model Engine on [{self.device}]...")
            
            # 1. Watsonx (API 기반이라 가벼움)
            self._init_watsonx()
            
            # 2. Local Models (메모리 사용량 주의)
            try:
                logger.info("loading BERT...")
                self.bert_model = HuggingFaceEmbeddings(
                    model_name=BERT_MODEL_NAME,
                    model_kwargs={'device': self.device},
                    encode_kwargs={'normalize_embeddings': True}
                )
            except Exception as e: logger.error(f"❌ BERT Failed: {e}")

            try:
                logger.info("loading CLIP Text...")
                self.clip_text_model = SentenceTransformer(CLIP_MODEL_NAME, device=self.device)
            except Exception as e: logger.error(f"❌ CLIP Text Failed: {e}")

            try:
                logger.info("loading CLIP Vision...")
                self.clip_vision_model = SentenceTransformer(CLIP_VISION_MODEL_NAME, device=self.device)
            except Exception as e: logger.error(f"❌ CLIP Vision Failed: {e}")

            self.is_initialized = True
            logger.info("✅ All Models Initialized Successfully.")

    def _init_watsonx(self):
        try:
            api_key = os.getenv("WATSONX_API_KEY")
            url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            
            if api_key and self.project_id:
                # [분석용] 정확한 묘사를 위해 greedy decoding 사용
                self.vision_model = ChatWatsonx(
                    model_id=VISION_MODEL_ID, url=url, apikey=api_key, project_id=self.project_id,
                    params={
                        "decoding_method": "greedy", 
                        "temperature": 0.0,
                        "max_new_tokens": 500,
                        "min_new_tokens": 10,
                        "repetition_penalty": 1.2
                    }
                )
                # [창작용] 텍스트 생성은 약간의 창의성 허용
                self.text_model = ChatWatsonx(
                     model_id=VISION_MODEL_ID, url=url, apikey=api_key, project_id=self.project_id,
                     params={
                        "decoding_method": "sample",
                        "temperature": 0.3,
                        "max_new_tokens": 600,
                     }
                )
                logger.info(f"✅ Watsonx Connected.")
            else:
                logger.warning("⚠️ Watsonx credentials missing.")
        except Exception as e: logger.error(f"❌ Watsonx Init Failed: {e}")

    # ----------------------------------------------------------------
    # Core Logic Methods
    # ----------------------------------------------------------------

    def generate_embedding(self, text: str) -> List[float]:
        """
        BERT 텍스트 임베딩 생성 (768차원)
        - 상품 등록 시 텍스트 기반 검색용 벡터 생성
        """
        if not self.bert_model:
            self.initialize()
        
        try:
            if self.bert_model:
                vector = self.bert_model.embed_query(text)
                return vector
            else:
                logger.warning("⚠️ BERT model not available, returning zeros")
                return [0.0] * 768
        except Exception as e:
            logger.error(f"❌ BERT embedding failed: {e}")
            return [0.0] * 768

    def calculate_similarity(self, text: str, image: Image.Image) -> float:
        """Reranking Logic: CLIP Score Calculation"""
        if not self.clip_text_model or not self.clip_vision_model:
            self.initialize()
        try:
            # 텍스트 임베딩 (캐싱 가능하나, 쿼리가 매번 다르므로 실시간 수행)
            text_emb = self.clip_text_model.encode(text, convert_to_tensor=True)
            # 이미지 임베딩
            img_emb = self.clip_vision_model.encode(image, convert_to_tensor=True)
            
            # 코사인 유사도 계산
            score = util.cos_sim(text_emb, img_emb).item()
            return score
        except Exception as e:
            logger.error(f"Similarity check failed: {e}")
            return 0.0

    def generate_dual_embedding(self, text: str) -> Dict[str, List[float]]:
        """BERT(검색용) + CLIP(시각적 매칭용) 동시 생성"""
        if not self.bert_model or not self.clip_text_model: self.initialize()
        
        result = {}
        # BERT
        if self.bert_model: 
            result["bert"] = self.bert_model.embed_query(text)
        else: 
            result["bert"] = [0.0] * 768
        
        # CLIP Text
        if self.clip_text_model:
            clip_emb = self.clip_text_model.encode(text)
            result["clip"] = clip_emb.tolist() if hasattr(clip_emb, "tolist") else clip_emb
        else: 
            result["clip"] = [0.0] * 512
            
        return result

    def generate_image_embedding(self, image_data: Union[str, Image.Image], use_yolo: bool = True) -> Dict[str, List[float]]:
        """
        이미지 -> CLIP Vector 변환 (DB 저장 및 검색용)
        
        Args:
            image_data: Base64 문자열 또는 PIL Image
            use_yolo: YOLO로 패션 영역 크롭 여부 (기본 True)
        """
        if not self.clip_vision_model: 
            self.initialize()
        try:
            pil_image = image_data
            if isinstance(image_data, str):
                # Base64 처리
                if "base64," in image_data: 
                    image_data = image_data.split("base64,")[1]
                pil_image = Image.open(io.BytesIO(base64.b64decode(image_data)))
            
            # ✅ YOLO로 패션 영역 크롭
            if use_yolo:
                try:
                    from src.core.yolo_detector import yolo_detector
                    cropped = yolo_detector.crop_fashion_regions(pil_image, target="full")
                    if cropped is not None:
                        pil_image = cropped
                        logger.info("✅ YOLO: Fashion region cropped for CLIP")
                except ImportError:
                    logger.warning("⚠️ YOLO not available, using original image")
                except Exception as e:
                    logger.warning(f"⚠️ YOLO crop failed: {e}, using original image")
            
            if self.clip_vision_model:
                vector = self.clip_vision_model.encode(pil_image)
                return {"clip": vector.tolist() if hasattr(vector, "tolist") else list(vector)}
            else:
                logger.warning("⚠️ CLIP Vision model not available")
                return {"clip": [0.0] * 512}
        except Exception as e:
            logger.error(f"🖼️ Image Embedding Error: {e}")
            return {"clip": [0.0] * 512}

    def generate_with_image(self, text_prompt: str, image_b64: str) -> str:
        """VLM Inference"""
        if not self.vision_model: 
            self.initialize()
        try:
            if not self.vision_model:
                logger.error("❌ Vision model not initialized")
                return "이미지 분석에 실패했습니다. (모델 미초기화)"
                
            message = HumanMessage(content=[
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ])
            return self.vision_model.invoke([message]).content
        except Exception as e:
            logger.error(f"Vision Error: {e}")
            return "이미지 분석에 실패했습니다."
            
    def generate_text(self, prompt: str) -> str:
        if not self.text_model: 
            self.initialize()
        try:
            if not self.text_model:
                return ""
            return self.text_model.invoke(prompt).content
        except Exception as e:
            logger.error(f"Text Gen Error: {e}")
            return ""

    def generate_fashion_embeddings(self, image_data: Union[str, Image.Image]) -> Dict[str, List[float]]:
        """
        ✅ 패션 특화 임베딩 - 전신/상의/하의 각각 CLIP 벡터 생성
        
        Returns:
            {
                "full": [512 dim vector],
                "upper": [512 dim vector],
                "lower": [512 dim vector]
            }
        """
        if not self.clip_vision_model: 
            self.initialize()
            
        result = {
            "full": [0.0] * 512,
            "upper": [0.0] * 512,
            "lower": [0.0] * 512
        }
        
        try:
            pil_image = image_data
            if isinstance(image_data, str):
                if "base64," in image_data: 
                    image_data = image_data.split("base64,")[1]
                pil_image = Image.open(io.BytesIO(base64.b64decode(image_data)))
            
            # YOLO로 각 영역 추출
            try:
                from src.core.yolo_detector import yolo_detector
                fashion_regions = yolo_detector.extract_fashion_features(pil_image)
                
                # 각 영역 CLIP 벡터 생성
                for region_name, region_img in fashion_regions.items():
                    if region_img is not None and self.clip_vision_model:
                        vector = self.clip_vision_model.encode(region_img)
                        result[region_name] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                        logger.info(f"✅ Generated CLIP vector for '{region_name}': {len(result[region_name])} dims")
                        
            except ImportError:
                logger.warning("⚠️ YOLO not available, using full image only")
                if self.clip_vision_model:
                    vector = self.clip_vision_model.encode(pil_image)
                    result["full"] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            except Exception as e:
                logger.warning(f"⚠️ YOLO failed: {e}, using full image")
                if self.clip_vision_model:
                    vector = self.clip_vision_model.encode(pil_image)
                    result["full"] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                    
        except Exception as e:
            logger.error(f"❌ Fashion embedding failed: {e}")
            
        return result

# 전역 인스턴스 생성
model_engine = ModelEngine()