import asyncio
import logging
import aiohttp
import base64
import re
from io import BytesIO
from typing import List, Dict, Any, Optional, Set
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
        
        # ✅ 유명인/연예인 이름 목록 (빠른 체크용)
        self.celebrity_names: Set[str] = {
            # 남자 아티스트/래퍼
            "지드래곤", "GD", "권지용", "지디",
            "빅뱅", "태양", "대성", "탑", "승리",
            "지코", "박재범", "사이먼도미닉", "그레이", "로꼬",
            # 여자 아이돌
            "장원영", "안유진", "이서", "가을", "레이",
            "카리나", "윈터", "지젤", "닝닝",
            "제니", "지수", "로제", "리사",
            "민지", "하니", "다니엘", "해린", "혜인",
            "카즈하", "사쿠라", "김채원", "허윤진", "홍은채",
            "태연", "윤아", "서현", "티파니", "제시카",
            "나연", "정연", "모모", "사나", "지효", "미나", "다현", "채영", "쯔위",
            "아이린", "슬기", "웬디", "조이", "예리",
            "츄", "희진", "현진", "고원", "김립",
            # 여자 배우
            "아이유", "수지", "송혜교", "김태리", "한소희", "전지현", "김고은",
            "신세경", "박보영", "설현", "박신혜", "손예진",
            "김유정", "김소현", "이성경", "서예지", "문가영",
            # 남자 아이돌
            "뷔", "정국", "지민", "RM", "슈가", "진", "제이홉",
            "민호", "태민", "온유", "키",
            "마크", "재현", "도영", "태용", "쟈니",
            "방찬", "리노", "창빈", "필릭스", "승민", "아이엔",
            "수빈", "연준", "범규", "태현", "휴닝카이",
            # 남자 배우
            "차은우", "공유", "현빈", "이종석", "박서준", "송강", "이도현",
            "박보검", "김수현", "이민호", "남주혁", "서강준",
            "송중기", "이준기", "지창욱", "박형식",
            # 해외 연예인
            "테일러스위프트", "아리아나그란데", "비욘세", "리한나",
            "젠데이아", "티모시샬라메", "톰홀랜드"
        }
        
        # ✅ 일반 명사 목록 (이름으로 오인하면 안 되는 단어들)
        self.common_words: Set[str] = {
            # 계절
            "겨울", "여름", "봄", "가을", "겨울에", "여름에", "봄에", "가을에",
            # 성별
            "남자", "여자", "남성", "여성", "남자옷", "여자옷", "남성복", "여성복",
            # 의류 종류
            "옷", "코트", "패딩", "자켓", "바지", "치마", "원피스", "셔츠", "니트",
            "가디건", "맨투맨", "후드", "티셔츠", "청바지", "슬랙스", "레깅스",
            "정장", "수트", "블라우스", "스커트", "조끼", "베스트", "점퍼",
            # 장소/상황
            "상갓집", "장례식", "결혼식", "식사", "식사자리", "모임", "파티",
            "출근", "퇴근", "데이트", "소개팅", "면접", "회사", "학교",
            "교회", "성당", "절", "명절", "추석", "설날", "크리스마스",
            # 형용사/부사
            "격식", "격식있는", "캐주얼", "편한", "따뜻한", "시원한", "가벼운",
            "무거운", "고급", "저렴한", "예쁜", "멋진", "세련된",
            # 동사/조사 어근
            "입을", "입을만한", "만한", "추천", "추천해줘", "보여줘", "찾아줘",
            "어울리는", "맞는", "좋은", "괜찮은",
            # 기타 일반 명사
            "어른", "어른들", "어른들과", "부모님", "친구", "동료", "선배", "후배",
            "함께", "함께하는", "같이", "혼자",
            "스타일", "패션", "코디", "룩", "착장", "차림",
            "상의", "하의", "아우터", "이너", "신발", "가방", "액세서리",
            # 시간
            "오늘", "내일", "주말", "평일", "아침", "저녁", "밤",
            # 조사/어미가 붙은 형태
            "에서", "에서의", "때", "때의", "용", "위한",
            # ✅ 추가: 자주 오인되는 일반 명사
            "자동차", "비행기", "기차", "버스", "지하철", "택시",
            "공항", "역", "터미널", "정류장",
            "사진", "이미지", "영상", "동영상", "뮤비",
            "콘서트", "공연", "무대", "행사", "이벤트",
            "브랜드", "명품", "빈티지", "레트로", "클래식",
            "트렌드", "유행", "인기", "핫한", "요즘"
        }
        
        # ✅ 패션 컨텍스트 키워드
        self.fashion_context_keywords = [
            "패션", "스타일", "코디", "룩", "착용", "의상",
            "공항", "시사회", "무대", "화보", "입은", "착장",
            "사복", "출근룩", "퇴근룩", "데이트룩"
        ]
        
        # ✅ 한글 이름 패턴 (2-3글자, 성+이름)
        self.korean_name_pattern = re.compile(r'^[가-힣]{2,3}$')

    async def _download_image(self, session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
        async with self.semaphore:
            try:
                timeout = aiohttp.ClientTimeout(total=4)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.google.com/"
                }
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.read()
                        image = Image.open(BytesIO(data)).convert("RGB")
                        if image.width < 250 or image.height < 250: return None
                        return image
            except Exception as e:
                logger.debug(f"Image download failed: {url} - {e}")
                return None
        return None

    def _image_to_base64(self, image: Image.Image) -> str:
        try:
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}"
        except Exception: return ""

    def _optimize_query_for_celebrity(self, user_query: str) -> str:
        """연예인 검색 쿼리 최적화"""
        stop_words = ["추천해줘", "보여줘", "찾아줘", "알려줘", "어때", "좀", "해줘"]
        
        words = user_query.split()
        keywords = []
        
        for w in words:
            clean_w = re.sub(r'(은|는|이|가|을|를|의|에|로|으로|와|과|도|만)$', '', w)
            if clean_w in stop_words or len(clean_w) < 2:
                continue
            keywords.append(clean_w)
        
        if not keywords:
            return user_query
            
        optimized = " ".join(keywords)
        logger.info(f"🔍 Query optimized: '{user_query}' -> '{optimized}'")
        return optimized

    def _get_scoring_context(self, query: str) -> str:
        if any(k in query for k in ["가방", "신발", "지갑", "액세서리"]): 
            return "close up product shot"
        return "full body fashion style"

    def _normalize_score(self, raw_score: float) -> int:
        if raw_score < 0.15: return 0
        normalized = (raw_score - 0.15) * 450
        return int(min(max(normalized, 60), 99))

    async def process_external_rag(self, query: str) -> Dict[str, Any]:
        """외부 이미지 검색 + VLM 분석 (연예인/유명인 검색 전용)"""
        logger.info(f"🌍 Processing EXTERNAL RAG: {query}")
        
        allowed, reason = quota_monitor.check_and_increment()
        if not allowed:
            logger.warning(f"⚠️ Quota exceeded: {reason}")
            return await self.process_internal_search(query)

        optimized_query = self._optimize_query_for_celebrity(query)
        
        logger.info(f"🔎 Searching Google Images: '{optimized_query}'")
        search_results = await self.search_client.search_images(
            optimized_query, num_results=15, start_index=1
        )
        
        if not search_results:
            logger.warning("❌ No search results from Google")
            return await self.process_internal_search(query)
            
        logger.info(f"✅ Found {len(search_results)} images")

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
                    
        logger.info(f"📊 Valid candidates: {len(scored_candidates)}")

        if not best_image:
            logger.warning("❌ No valid images after scoring")
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

    async def _analyze_image_with_vlm(self, image_data: Any, query: str) -> str:
        """VLM을 이용한 이미지 분석"""
        try:
            if isinstance(image_data, Image.Image):
                img_b64 = self._image_to_base64(image_data).split(",")[1]
            else:
                img_b64 = image_data

            vlm_prompt = f"""
            당신은 정직한 패션 에디터입니다.
            **오직 이미지에 시각적으로 보이는 것만** 설명하세요. 
            이미지에 없는 내용(상상, 배경지식, 추측)은 절대 포함하지 마세요.
            
            사용자 질문: "{query}" (참고용일 뿐, 실제 이미지 내용이 우선입니다.)
            
            [분석 가이드]
            1. **트렌드 무드**: 이미지에서 느껴지는 실제 분위기만 한 줄로 작성.
            2. **스타일링 포인트**: 눈에 보이는 옷의 색상, 소재, 핏을 구체적으로 묘사.
            3. **추천 아이템**: 이 사진 속 인물이 착용한 아이템과 유사한 제품 추천.
            
            반드시 한국어로 작성하세요.
            """
            return self.engine.generate_with_image(vlm_prompt, img_b64)
        except Exception as e:
            logger.error(f"VLM analysis failed: {e}")
            return "분석 불가"

    async def process_internal_search(self, query: str) -> Dict[str, Any]:
        """내부 텍스트 검색 (일반 상품 검색)"""
        logger.info(f"📦 Processing INTERNAL search: {query}")
        vectors = self.engine.generate_dual_embedding(query)
        return {
            "vectors": vectors,
            "search_path": "INTERNAL",
            "strategy": "internal_text",
            "ai_analysis": None,
            "description": f"'{query}' 내부 검색 결과",
            "ref_image": None
        }

    def _extract_potential_names(self, query: str) -> List[str]:
        """
        쿼리에서 잠재적인 인물 이름 추출
        - 2-3글자 한글 단어 중 일반 명사가 아닌 것
        """
        # 공백으로 분리
        words = query.split()
        potential_names = []
        
        for word in words:
            # 조사 제거
            clean_word = re.sub(r'(은|는|이|가|을|를|의|에|로|으로|와|과|도|만|처럼|같은)$', '', word)
            
            # 2-3글자 한글인지 체크
            if not self.korean_name_pattern.match(clean_word):
                continue
            
            # 일반 명사인지 체크
            if clean_word in self.common_words:
                continue
            
            # 일반 명사의 일부인지 체크 (예: "겨울에" → "겨울")
            is_common = False
            for common in self.common_words:
                if clean_word in common or common in clean_word:
                    is_common = True
                    break
            
            if not is_common:
                potential_names.append(clean_word)
        
        return potential_names

    def _contains_celebrity(self, query: str) -> Optional[str]:
        """
        ✅ 스마트한 연예인/유명인 감지
        
        1단계: 알려진 연예인 목록에서 체크 (빠름)
        2단계: 한글 이름 패턴(2-3글자) 중 일반 명사 아닌 것 감지 (허경영 같은 경우)
        """
        query_normalized = query.replace(" ", "")
        
        # 1단계: 알려진 연예인 이름 체크
        for name in self.celebrity_names:
            if name in query_normalized:
                logger.info(f"🎯 Known celebrity found: '{name}'")
                return name
        
        # 2단계: 잠재적 이름 추출 (일반 명사 제외)
        potential_names = self._extract_potential_names(query)
        
        if potential_names:
            # 패션 컨텍스트 키워드가 있는지 확인
            has_fashion_context = any(k in query for k in self.fashion_context_keywords)
            
            if has_fashion_context:
                logger.info(f"🎯 Potential person name detected: {potential_names} with fashion context")
                return potential_names[0]
        
        return None

    async def determine_search_path(self, query: str) -> str:
        """
        ✅ 스마트한 검색 경로 결정
        
        EXTERNAL 조건 (Google 이미지 검색):
        - 알려진 연예인 이름이 포함된 경우
        - 잠재적 인물 이름(2-3글자, 비일반명사) + 패션 키워드 조합
        
        INTERNAL 조건 (내부 DB 검색):
        - 일반적인 상품 검색
        - 상황 기반 추천 (상갓집, 결혼식 등)
        
        예시:
        - "장원영 공항패션" → EXTERNAL (알려진 연예인)
        - "허경영 패션" → EXTERNAL (2글자 이름 + 패션)
        - "김철수 스타일" → EXTERNAL (3글자 이름 + 스타일)
        - "겨울 남자옷 추천" → INTERNAL (일반 검색)
        - "상갓집 옷 추천" → INTERNAL (상황 기반)
        - "격식있는 식사자리 옷" → INTERNAL (상황 기반)
        """
        
        # 연예인/유명인 이름 감지
        celebrity = self._contains_celebrity(query)
        
        if celebrity:
            logger.info(f"🌍 Celebrity/Person search: '{celebrity}' in '{query}' -> EXTERNAL")
            return 'EXTERNAL'
        
        # 일반 검색은 INTERNAL
        logger.info(f"📦 General product search: '{query}' -> INTERNAL")
        return 'INTERNAL'


rag_orchestrator = AIOrchestrator()