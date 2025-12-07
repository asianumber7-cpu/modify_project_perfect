import asyncio
import logging
import aiohttp
import base64
import re
from io import BytesIO
from typing import List, Dict, Any, Optional
from PIL import Image

from src.core.model_engine import model_engine
from src.services.quota_monitor import quota_monitor
from src.services.google_search_client import GoogleSearchClient

logger = logging.getLogger(__name__)

class AIOrchestrator:
    def __init__(self):
        self.engine = model_engine
        self.search_client = GoogleSearchClient()
        self.semaphore = asyncio.Semaphore(5)

    async def _download_image(self, session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
        async with self.semaphore:
            try:
                timeout = aiohttp.ClientTimeout(total=4)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.google.com/"
                }
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.read()
                        image = Image.open(BytesIO(data)).convert("RGB")
                        if image.width < 250 or image.height < 250: return None
                        return image
            except Exception: return None
        return None

    # [수정] 화질 개선 (85 -> 95)
    def _image_to_base64(self, image: Image.Image) -> str:
        try:
            buffered = BytesIO()
            # [핵심] VLM이 디테일을 볼 수 있도록 고화질 유지
            image.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}"
        except Exception: return ""

    def _optimize_query(self, user_query: str) -> str:
        # (기존 코드 유지: 조사 제거 및 LLM 최적화)
        prompt = f"""
        Role: Search Query Optimizer.
        Task: Convert natural language to short keywords.
        Input: "{user_query}"
        
        Rules:
        1. Remove Particles: Remove Korean particles like '가', '는', '을', '를'.
        2. Remove Context: Remove "10분만에", "꼬신", "남자".
        3. Output: "Celebrity Name" + "Style Keywords" (e.g. "Lee Hyori Y2K Fashion").
        """
        try:
            optimized = self.engine.generate_text(prompt).strip()
            if len(optimized) < 30 and len(optimized) > 2:
                return optimized
        except: pass

        words = user_query.split()
        keywords = []
        stop_words = ["추천해줘", "보여줘", "찾아줘", "알려줘", "어때", "사진", "이미지", "10분만에", "꼬셨던", "남자"]
        
        for w in words:
            clean_w = re.sub(r'(은|는|이|가|을|를|의|에|로)$', '', w)
            if clean_w not in stop_words and len(clean_w) > 1:
                keywords.append(clean_w)
        
        if not keywords: return user_query
        return " ".join(keywords)

    def _get_scoring_context(self, query: str) -> str:
        if any(k in query for k in ["가방", "신발", "지갑"]): return "close up product shot"
        return "full body fashion style"

    def _normalize_score(self, raw_score: float) -> int:
        if raw_score < 0.15: return 0
        normalized = (raw_score - 0.15) * 450
        return int(min(max(normalized, 60), 99))

    async def process_external_rag(self, query: str) -> Dict[str, Any]:
        logger.info(f"🌍 Processing EXTERNAL RAG: {query}")
        allowed, _ = quota_monitor.check_and_increment()
        if not allowed: return await self.process_internal_search(query)

        optimized_query = self._optimize_query(query)
        
        search_results = await self.search_client.search_images(
            optimized_query, num_results=15, start_index=1
        )
        
        if not search_results: return await self.process_internal_search(query)

        best_image = None
        candidates_data = []

        async with aiohttp.ClientSession() as session:
            tasks = [self._download_image(session, item['link']) for item in search_results]
            downloaded_images = await asyncio.gather(*tasks)

            scored_candidates = []
            clip_prompt = f"{optimized_query} {self._get_scoring_context(optimized_query)}"

            for i, img in enumerate(downloaded_images):
                if img:
                    base_score = self.engine.calculate_similarity(clip_prompt, img)
                    ratio_bonus = 0.05 if img.height > img.width else 0.0
                    final_score = base_score + ratio_bonus

                    if final_score > 0.18:
                        scored_candidates.append({
                            "image": img,
                            "url": search_results[i]['link'],
                            "raw_score": final_score,
                            "display_score": self._normalize_score(final_score)
                        })

            scored_candidates.sort(key=lambda x: x['raw_score'], reverse=True)
            top_candidates = scored_candidates[:4]

            if top_candidates:
                best_candidate = top_candidates[0]
                best_image = best_candidate['image']
                
                for cand in top_candidates:
                    candidates_data.append({
                        "image_base64": self._image_to_base64(cand['image']),
                        "score": cand['display_score']
                    })

        if not best_image:
            return await self.process_internal_search(query)

        summary = await self._analyze_image_with_vlm(best_image, query)
        final_data_uri = self._image_to_base64(best_image)

        vectors = {
            "bert": self.engine.generate_dual_embedding(summary)["bert"],
            "clip": self.engine.generate_image_embedding(best_image)["clip"]
        }

        return {
            "vectors": vectors,
            "search_path": "EXTERNAL",
            "strategy": "visual_rag_vlm",
            "ai_analysis": {
                "summary": summary,
                "reference_image": final_data_uri,
                "candidates": candidates_data
            },
            "description": summary,
            "ref_image": final_data_uri
        }

    async def analyze_specific_image(self, image_b64: str, query: str) -> str:
        try:
            if "base64," in image_b64:
                image_b64 = image_b64.split("base64,")[1]
            return await self._analyze_image_with_vlm(image_b64, query)
        except Exception:
            return "이미지 분석에 실패했습니다."

    # [핵심 수정] VLM 분석 프롬프트 강화 (Grounding)
    async def _analyze_image_with_vlm(self, image_data: Any, query: str) -> str:
        try:
            if isinstance(image_data, Image.Image):
                img_b64 = self._image_to_base64(image_data).split(",")[1]
            else:
                img_b64 = image_data

            # [Grounding Prompt] "보이는 것만 묘사하라"는 강력한 제약 추가
            vlm_prompt = f"""
            당신은 정직한 패션 에디터입니다.
            **오직 이미지에 시각적으로 보이는 것만** 설명하세요. 
            이미지에 없는 내용(상상, 배경지식, 추측)은 절대 포함하지 마세요.
            
            사용자 질문: "{query}" (참고용일 뿐, 실제 이미지 내용이 우선입니다.)
            
            [분석 가이드]
            1. **트렌드 무드**: 이미지에서 느껴지는 실제 분위기만 한 줄로 작성.
            2. **스타일링 포인트**: 눈에 보이는 옷의 색상, 소재, 핏을 구체적으로 묘사 (예: "검은색 가죽 자켓", "파란색 데님 팬츠").
            3. **추천 아이템**: 이 사진 속 인물이 착용한 아이템과 유사한 제품 추천.
            
            반드시 한국어로 작성하세요.
            """
            return self.engine.generate_with_image(vlm_prompt, img_b64)
        except Exception:
            return "분석 불가"

    async def process_internal_search(self, query: str) -> Dict[str, Any]:
        vectors = self.engine.generate_dual_embedding(query)
        return {
            "vectors": vectors,
            "search_path": "INTERNAL",
            "strategy": "internal_text",
            "ai_analysis": None,
            "description": f"'{query}' 내부 검색 결과",
            "ref_image": None
        }

    async def determine_search_path(self, query: str) -> str:
        external_triggers = ["스타일", "코디", "패션", "룩", "유행", "연예인", "공항", "입은", "추천"]
        if any(t in query for t in external_triggers): return 'EXTERNAL'
        return 'INTERNAL'

rag_orchestrator = AIOrchestrator()