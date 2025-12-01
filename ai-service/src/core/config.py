import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field # Field 임포트하여 기본값 명시적으로 설정

class Settings(BaseSettings):
    # Core Settings
    PROJECT_NAME: str = Field("MODIFY AI Service", description="프로젝트 이름")
    ENVIRONMENT: str = Field(os.getenv("ENVIRONMENT", "development"), description="실행 환경")

    # Redis Settings (Quota Monitor 및 Celery Broker 용)
    REDIS_HOST: str = Field(os.getenv("REDIS_HOST", "redis"), description="Redis 서버 호스트")
    REDIS_PORT: int = Field(int(os.getenv("REDIS_PORT", 6379)), description="Redis 서버 포트")
    
    # AI Model Settings (HuggingFace/LangChain 기반)
    # CLIP 대신 범용 768차원 임베딩 모델을 사용함을 명시
    EMBEDDING_MODEL_NAME: str = Field("sentence-transformers/all-mpnet-base-v2", description="768차원 임베딩 모델 이름")
    EMBEDDING_DIMENSION: int = Field(768, description="벡터 차원 (768D)")
    EMBEDDING_DEVICE: str = Field(os.getenv("EMBEDDING_DEVICE", "cpu"), description="임베딩 모델 실행 장치 (cpu/cuda)")
    
    # LLM Settings (Groq, WatsonX 등 LLM 연동 설정)
    GROQ_API_KEY: str = Field(os.getenv("GROQ_API_KEY", ""), description="Groq API 키 (LLM 추론용)")
    LLM_MODEL_NAME: str = Field("llama3-8b-8192", description="텍스트 추론에 사용할 LLM 모델 이름")
    
    # Google API Settings (RAG용)
    GOOGLE_API_KEY: str = Field(os.getenv("GOOGLE_API_KEY", ""), description="Google Custom Search API 키")
    GOOGLE_SEARCH_ENGINE_ID: str = Field(os.getenv("GOOGLE_SEARCH_ENGINE_ID", ""), description="Google Custom Search Engine ID (CX)")
    GOOGLE_API_DAILY_QUOTA: int = Field(int(os.getenv("GOOGLE_API_DAILY_QUOTA", 100)), description="Google Search API 일일 허용 쿼터")
    
    # Vision API Settings (Llama Vision, YOLO/DINOv2 분석 결과 전송용)
    # Vision 모델이 별도 마이크로서비스로 분리되어 있다고 가정합니다.
    VISION_API_URL: str = Field(os.getenv("VISION_API_URL", "http://vision-service:8000/analyze"), description="Vision 분석 마이크로서비스 URL")

    # Pydantic V2 설정 방식
    model_config = SettingsConfigDict(env_file=".env.dev", extra='ignore')

settings = Settings()