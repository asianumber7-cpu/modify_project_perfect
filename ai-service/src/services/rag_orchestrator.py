import os
import asyncio
import base64
from typing import List, Dict, Any, Optional
import logging
import aiohttp
from io import BytesIO
from PIL import Image
from googleapiclient.discovery import build # Google API Client (동기)

from src.core.model_engine import model_engine
from src.services.quota_monitor import quota_monitor # 쿼터 모니터 필요
from src.core.config import settings # 설정 필요

logger = logging.getLogger(__name__)

class AIOrchestrator:
    """
    사용자 쿼리를 받아 검색 유형을 결정하고, 
    Vision, RAG, Vector Embedding 파이프라인을 지휘하는 중앙 컨트롤러.
    """
    def __init__(self):
        self.engine = model_engine
        self.semaphore = asyncio.Semaphore(5) # 이미지 병렬 다운로드 제어

    # -------------------------------------------------------------
    # RAG: Google Search 및 이미지 처리 (새로 주신 코드 통합)
    # -------------------------------------------------------------
    def _google_image_search(self, query: str, num: int = 5) -> Dict[str, Any]:
        """ Google Image Search API 호출 (동기) """
        is_allowed, remaining = quota_monitor.check_and_increment()
        
        if not is_allowed:
            logger.warning("⚠️ Google API Quota Exceeded!")
            return {"error": "quota_exceeded", "items": []}
            
        try:
            # Google API Build는 동기 함수입니다.
            service = build("customsearch", "v1", developerKey=settings.GOOGLE_API_KEY)
            res = service.cse().list(
                q=query, 
                cx=settings.GOOGLE_SEARCH_ENGINE_ID, 
                searchType="image", 
                num=num
            ).execute()
            return {"items": res.get("items", [])}
        except Exception as e:
            logger.error(f"❌ Google Search API Error: {e}")
            return {"error": "api_error", "items": []}

    async def _download_and_process_image(self, session: aiohttp.ClientSession, url: str):
        """ 이미지 다운로드 및 PIL Image 객체 반환 (비동기, 병렬) """
        async with self.semaphore:
            try:
                # [Critical] 10초 타임아웃 설정
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.read()
                        # NOTE: Image.open은 I/O 블로킹 작업이므로 Celery에서는 Process Pool에서 실행해야 안전함.
                        # 여기서는 Celery Task가 아닌 FastAPI 비동기 환경에서 사용한다고 가정하고 진행.
                        image = Image.open(BytesIO(data)).convert("RGB")
                        return image
            except Exception as e:
                logger.warning(f"⚠️ Image download skipped ({url}): {str(e)}")
                return None
    
    # -------------------------------------------------------------
    # 핵심 비즈니스 로직 (LLM 기반 추론 및 경로 결정)
    # -------------------------------------------------------------

    async def determine_search_path(self, query: str) -> str:
        """
        쿼리가 INTERNAL(색상/형태)인지 EXTERNAL(트렌드/RAG)인지 LLM에게 물어 결정합니다.
        (로직은 이전 코드와 동일하게 유지)
        """
        internal_keywords = ["빨간색", "니트", "코트", "바지", "가격", "재질", "색상", "비슷한 가격", "비슷한 색상", "다른 브랜드"]
        if any(kw in query for kw in internal_keywords):
             return 'INTERNAL'

        prompt = f"""
        주어진 쿼리가 실시간/외부 트렌드(예: 연예인, 사건, 최신 기술)를 참조해야 하는 복잡한 검색이면 'EXTERNAL', 
        단순히 DB 내 상품 속성(색상, 카테고리 등)으로 해결 가능하면 'INTERNAL'로만 답변하세요.
        쿼리: "{query}"
        """
        
        try:
            decision_text = await self.engine.get_llm_response(prompt)
            if 'EXTERNAL' in decision_text.upper():
                return 'EXTERNAL'
            return 'INTERNAL'
        except Exception as e:
            logger.error(f"Path determination failed: {e}")
            return 'INTERNAL'

    async def process_internal_search(self, query: str) -> Dict[str, Any]:
        """
        INTERNAL Path: 쿼리 벡터화 및 핵심 키워드 추출
        """
        core_prompt = f"'{query}'에서 상품 검색을 위한 가장 중요한 키워드와 스타일 속성(예: 오버핏, 캐주얼)을 5개 단어 이하로 추출하고 쉼표로 구분하시오."
        core_text = await self.engine.get_llm_response(core_prompt)
        
        # 768차원 벡터 생성
        vector = self.engine.generate_embedding(core_text)
        
        return {"vector": vector, "keyword": core_text}

    async def process_external_rag(self, query: str, image_b64: Optional[str] = None) -> Dict[str, Any]:
        """
        EXTERNAL Path: Google Search -> RAG/Vision 분석 -> 벡터 생성
        """
        # 1. Google Search를 통해 이미지/텍스트 컨텍스트 확보
        search_res = self._google_image_search(query)
        items = search_res.get("items", [])
        
        # 2. 이미지 다운로드 및 PIL 객체 리스트 생성
        async with aiohttp.ClientSession() as session:
            tasks = [self._download_and_process_image(session, item['link']) for item in items]
            images: List[Optional[Image.Image]] = await asyncio.gather(*tasks)

        valid_images: List[Image.Image] = [img for img in images if img is not None]
        
        vision_analysis = ""
        if image_b64 or valid_images:
            # 3. Vision 분석 (Llama Vision 또는 YOLO/DINOv2)
            # YOLO/DINOv2를 사용한 객체 탐지 및 스타일 분석 로직은 Celery Task로 분리해야 합니다.
            # 여기서는 분석 요청만 보낸다고 가정합니다.
            
            # TODO: 여기에 Vision API 호출 로직 구현
            vision_analysis = "Vision Model: 이미지에서 핵심 상품(예: 블랙 코트) 및 스타일이 분석되었습니다."

        # 4. RAG 컨텍스트 확보 및 LLM 요약
        context = "\n".join([r.get('snippet', '') for r in items])
        
        rag_prompt = f"""
        다음 컨텍스트(외부 검색 결과 및 시각 분석)를 바탕으로 사용자의 쿼리에 가장 적합한 상품 검색 키워드를 5개 이하로 추출하고, 그 결과를 바탕으로 사용자에게 제공할 짧은 추천 이유(1문장)를 작성하세요.
        
        [컨텍스트]
        {context}
        {vision_analysis}
        
        [출력 형식]
        KEYWORD: 키워드1, 키워드2, 키워드3, ...
        REASON: 추천 이유 문장
        
        사용자 쿼리: {query}
        """

        rag_response = await self.engine.get_llm_response(rag_prompt)
        
        # 응답 파싱
        keyword_line = next((line for line in rag_response.split('\n') if line.startswith('KEYWORD:')), '')
        reason_line = next((line for line in rag_response.split('\n') if line.startswith('REASON:')), '')
        
        keywords = keyword_line.replace("KEYWORD:", "").strip()
        reason = reason_line.replace("REASON:", "").strip()
        
        # 5. 최종 검색 키워드를 임베딩하여 벡터 생성
        vector = self.engine.generate_embedding(keywords)
        
        # 검색 소스 정리
        search_sources = [{"title": item.get('title'), "url": item.get('link')} for item in items]

        return {
            "vector": vector, 
            "keyword": keywords,
            "reason": reason,
            "search_sources": search_sources
        }

rag_orchestrator = AIOrchestrator()