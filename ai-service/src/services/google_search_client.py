import os
import httpx
from typing import List, Dict, Any

# Google Custom Search Engine (CSE) API 키 및 ID (환경 변수 필요)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

class GoogleSearchClient:
    """
    Google Custom Search Engine API를 사용하여 외부 검색 데이터를 가져옵니다.
    """
    def __init__(self):
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            # 실무에서는 더 견고한 에러 처리가 필요함
            print("⚠️ WARNING: GOOGLE_API_KEY or GOOGLE_CSE_ID is missing for RAG.")
            self.is_ready = False
        else:
            self.is_ready = True

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        비동기로 Google 검색을 실행합니다.
        """
        if not self.is_ready:
            return [{"source": "Internal", "snippet": "Google Search API Not Configured."}]

        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": num_results,
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(SEARCH_URL, params=params)
                response.raise_for_status() 
                data = response.json()
                
                snippets = []
                for item in data.get("items", []):
                    snippets.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "url": item.get("link", "")
                    })
                return snippets
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error during Google Search: {e}")
                return [{"source": "Error", "snippet": f"Google API returned error: {e.response.status_code}"}]
            except Exception as e:
                print(f"Network or other error: {e}")
                return [{"source": "Error", "snippet": f"Search failed: {e}"}]