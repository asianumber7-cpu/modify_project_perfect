import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mic, Heart, Send, Sparkles } from 'lucide-react';
import { useVoiceControl } from '@/hooks/useVoiceControl'; // 훅 임포트
import { useSearchStore } from '@/store/searchStore';

export default function Home() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');

  const { addRecentSearch } = useSearchStore();

  // 🎤 음성 인식 훅 연결
  const { isListening, startListening } = useVoiceControl((text) => {
    // 기존 입력값 뒤에 음성 인식 텍스트 추가 (띄어쓰기 포함)
    setPrompt((prev) => (prev ? `${prev} ${text}` : text));
  });

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim()) return;

    addRecentSearch(prompt.trim());
    navigate(`/search?q=${encodeURIComponent(prompt)}`);
  };

  const handleKeywordClick = (keyword: string) => {
    navigate(`/search?q=${encodeURIComponent(keyword)}`);
  };

  // 디자인 시안에 맞춘 데이터
  const topKeywords = ['봄 데이트룩', '미니멀', '오피스룩', '빈티지'];
  
  const promptCards = [
    { text: "다가오는 벚꽃 축제, 화사하게 입고 싶은데 남자친구랑 시밀러 룩 추천해줘" },
    { text: "바리스타로서의 매력이 좋아보이는 편안한 룩을 검색해줘" },
    { text: "어른들과 함께하는 격식있는 식사자리에서 입을 만한 마무리 검색해줘" },
    { text: "해외여행을 앞두고 캐주얼한 복장과 간편한 착장을 추천해줘" },
  ];

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-4 py-8 bg-white dark:bg-black text-gray-900 dark:text-white transition-colors duration-300">
      
      {/* 1. 메인 타이틀 */}
      <h1 className="text-3xl md:text-5xl font-bold mb-12 text-center bg-clip-text text-transparent bg-gradient-to-r from-purple-500 to-blue-500">
        원하시는 스타일이 무엇인가요?
      </h1>

      {/* 2. 상단 키워드 버튼 (Pill shape) */}
      <div className="flex flex-wrap justify-center gap-4 mb-8 w-full max-w-5xl">
        {topKeywords.map((keyword, idx) => (
          <button
            key={idx}
            onClick={() => handleKeywordClick(keyword)}
            className="px-8 py-3 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 font-medium hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors shadow-sm"
          >
            {keyword}
          </button>
        ))}
      </div>

      {/* 3. 추천 프롬프트 카드 (Grid) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 w-full max-w-5xl mb-10">
        {promptCards.map((card, idx) => (
          <div
            key={idx}
            onClick={() => setPrompt(card.text)}
            className="p-5 bg-gray-100 dark:bg-gray-800 rounded-2xl cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-all text-sm leading-relaxed text-gray-700 dark:text-gray-300 shadow-sm flex items-center"
          >
            {card.text}
          </div>
        ))}
      </div>

      {/* 4. 대형 입력창 (Input Area) - 이미지 디자인 반영 */}
      <div className="w-full max-w-5xl relative">
        <div className="relative bg-gray-100 dark:bg-gray-800 rounded-3xl p-4 min-h-[160px] shadow-inner border border-transparent focus-within:border-purple-500 transition-all flex flex-col">
          
          <div className="flex gap-4 h-full flex-1">
            {/* 🎤 왼쪽: 마이크 버튼 (보라색 사각형) */}
            <div className="flex flex-col gap-2">
                <button 
                    onClick={startListening}
                    className={`w-12 h-12 rounded-xl flex items-center justify-center text-white transition-all shadow-md
                        ${isListening ? 'bg-red-500 animate-pulse' : 'bg-purple-600 hover:bg-purple-700'}
                    `}
                    title="음성으로 입력하기"
                >
                    <Mic size={24} />
                </button>
            </div>

            {/* 📝 중앙: 텍스트 입력 영역 */}
            <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSearch();
                    }
                }}
                placeholder={isListening ? "말씀해주세요..." : "원하는 스타일을 입력하거나 위의 예시를 드래그 해주세요"}
                className="w-full bg-transparent border-none outline-none text-lg resize-none placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white pt-2 leading-relaxed"
            />
          </div>

          {/* 하단 컨트롤 영역 (Wishlist, 글자수, 전송) */}
          <div className="flex justify-between items-end mt-4 pl-[4rem]"> {/* 마이크 버튼 너비만큼 padding left */}
            
            {/* Wishlist 버튼 */}
            <button className="flex items-center gap-2 px-4 py-2 bg-black dark:bg-white/10 text-white rounded-lg text-sm font-medium hover:opacity-80 transition-opacity">
                <Heart size={16} className="fill-current text-red-500" />
                Wishlist
            </button>

            <div className="flex items-center gap-4">
                {/* 글자수 표시 */}
                <span className="text-xs text-gray-400">
                    {prompt.length} / 1000
                </span>

                {/* 전송 버튼 (엔터 키 아이콘 느낌) */}
                <button 
                    onClick={() => handleSearch()}
                    disabled={!prompt.trim()}
                    className="p-2 text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 transition-colors disabled:opacity-30"
                >
                    <Send size={20} />
                </button>
            </div>
          </div>

        </div>
        
        {/* 음성 인식 중 상태 메시지 (선택 사항) */}
        {isListening && (
            <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-black/80 text-white px-4 py-2 rounded-full text-sm animate-bounce">
                🎧 듣고 있어요...
            </div>
        )}
      </div>

    </div>
  );
}