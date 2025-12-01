import os
import logging
from typing import List, Optional

# 🚨 FIX: langchain_community가 아닌 langchain_ibm 사용
from langchain_ibm import WatsonxLLM
from langchain_huggingface import HuggingFaceEmbeddings

# 로깅 설정
logger = logging.getLogger(__name__)

# --- 설정 ---
EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# LLM_MODEL_ID = "ibm/granite-13b-chat-v2" 
LLM_MODEL_ID = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")

class ModelEngine:
    _instance: Optional['ModelEngine'] = None
    
    def __init__(self):
        self.text_llm: Optional[WatsonxLLM] = None
        self.embedding_model: Optional[HuggingFaceEmbeddings] = None
        self.is_initialized = False

    def initialize(self):
        """모델을 초기화하고 메모리에 로드합니다."""
        logger.info(f"🚀 Initializing Model Engine...")
        
        try:
            # 1. WatsonxLLM 초기화 (실패해도 임베딩은 로드 시도하도록 try-except 분리)
            try:
                watsonx_api_key = os.getenv("WATSONX_API_KEY")
                project_id = os.getenv("WATSONX_PROJECT_ID")
                url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

                if watsonx_api_key and project_id:
                    self.text_llm = WatsonxLLM(
                        model_id=LLM_MODEL_ID,
                        url=url,
                        apikey=watsonx_api_key,
                        project_id=project_id,
                        params={
                            "decoding_method": "greedy",
                            "max_new_tokens": 512,
                            "min_new_tokens": 1,
                            "temperature": 0.5
                        }
                    )
                    logger.info("✅ Watsonx LLM Loaded.")
                else:
                    logger.warning("⚠️ Watsonx credentials not found. LLM disabled.")
            except Exception as e:
                logger.error(f"❌ Watsonx LLM Init Failed: {e}")

            # 2. 임베딩 모델 초기화 (여기가 핵심)
            logger.info(f"📥 Loading Embedding Model: {EMBEDDING_MODEL_NAME}...")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                model_kwargs={'device': os.getenv("EMBEDDING_DEVICE", "cpu")},
                encode_kwargs={'normalize_embeddings': True}
            )
            logger.info("✅ Embedding Model Loaded.")
            
            self.is_initialized = True
            
        except Exception as e:
            logger.error(f"❌ Critical Error in Model Engine Init: {e}")
            # 여기서 에러를 raise 하지 않고, 개별 메서드에서 재시도하게 함

    def generate_embedding(self, text: str) -> List[float]:
        """
        텍스트 -> 벡터 변환 (자동 복구 기능 포함)
        """
        # 🚨 [Auto-Recovery] 모델이 없으면 로딩 시도
        if not self.embedding_model:
            logger.warning("⚠️ Embedding model not ready. Attempting lazy load...")
            self.initialize()
            
        if not self.embedding_model:
             # 재시도 후에도 없으면 진짜 에러
            raise RuntimeError("Embedding model is completely failed.")
            
        return self.embedding_model.embed_query(text)

    def generate_text(self, prompt: str) -> str:
        """
        LLM 텍스트 생성 (자동 복구 기능 포함)
        """
        if not self.text_llm:
            logger.warning("⚠️ LLM not ready. Attempting lazy load...")
            self.initialize()
        
        if not self.text_llm:
            return "AI Model is not available."

        return self.text_llm.invoke(prompt)

# 싱글톤 인스턴스
model_engine = ModelEngine()