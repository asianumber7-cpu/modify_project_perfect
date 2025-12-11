import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Search as SearchIcon, Mic, X, Sparkles, TrendingUp, 
  ImageIcon, ShoppingBag, AlertCircle, RefreshCw, ArrowUp, Check
} from 'lucide-react';
import client from '../api/client';
import ProductCard from '../components/product/ProductCard';
import { useSearchStore } from '../store/searchStore';

// --- Types ---
interface ProductResponse {
    id: number;
    name: string;
    description: string;
    price: number;
    category: string;
    image_url: string;
    stock_quantity: number;
    in_stock?: boolean;
    gender?: string;
    is_active?: boolean;
}

interface CandidateImage {
    image_base64: string;
    score: number;
}

interface SearchResult {
    status: string;
    ai_analysis?: {
        summary: string;
        reference_image?: string;
        candidates?: CandidateImage[];
    };
    products: ProductResponse[];
}

const API_ENDPOINT = '/search/ai-search';

const useSearchQuery = () => {
    const [searchParams] = useSearchParams();
    return searchParams.get('q') || '';
};

const useTTS = () => {
    const speak = useCallback((text: string) => {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'ko-KR';
            utterance.rate = 1.0; 
            window.speechSynthesis.speak(utterance);
        }
    }, []);
    return { speak };
};

const LOADING_STEPS = [
    { text: "글로벌 트렌드를 검색하고 있습니다...", icon: "🌍" },
    { text: "가장 적절한 이미지를 선별 중입니다...", icon: "🖼️" },
    { text: "패션 스타일과 핏을 정밀 분석 중입니다...", icon: "✨" },
    { text: "Vogue 스타일 칼럼을 작성하고 있습니다...", icon: "📝" }
];

export default function Search() {
    const queryTextFromUrl = useSearchQuery();
    const { addRecentSearch } = useSearchStore();

    const [query, setQuery] = useState(queryTextFromUrl);
    const [imageFile, setImageFile] = useState<File | null>(null);
    const [results, setResults] = useState<ProductResponse[]>([]);
    
    // AI 분석 상태
    const [aiAnalysis, setAiAnalysis] = useState<SearchResult['ai_analysis'] | null>(null);
    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [currentText, setCurrentText] = useState<string>("");
    
    // 원본 검색어 저장 (CLIP 검색 시 성별 필터용)
    const [originalQuery, setOriginalQuery] = useState<string>("");
    
    // UI 상태
    const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
    const [isSearchingProducts, setIsSearchingProducts] = useState(false);
    const [showProducts, setShowProducts] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [loadingStepIndex, setLoadingStepIndex] = useState(0); 
    const [timestamp, setTimestamp] = useState<number>(Date.now());

    const fileInputRef = useRef<HTMLInputElement>(null);
    const productSectionRef = useRef<HTMLDivElement>(null);
    const { speak } = useTTS();

    useEffect(() => {
        if (isLoading) {
            const interval = setInterval(() => {
                setLoadingStepIndex((prev) => (prev + 1) % LOADING_STEPS.length);
            }, 800); 
            return () => clearInterval(interval);
        } else {
            setLoadingStepIndex(0);
        }
    }, [isLoading]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file && file.type.startsWith('image/')) setImageFile(file);
    };

    // ✅ 백엔드 API URL
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    // ✅ 이미지 URL 변환 + 캐시 버스팅
    const getBustedImage = (url: string) => {
        if (!url) return 'https://placehold.co/400x500/e2e8f0/64748b?text=No+Image';
        if (url.startsWith('data:')) return url;
        if (url.startsWith('http://') || url.startsWith('https://')) {
            const separator = url.includes('?') ? '&' : '?';
            return `${url}${separator}t=${timestamp}`;
        }
        // /static/images/... 형식 → 백엔드 URL 붙이기
        if (url.startsWith('/static/')) {
            return `${API_BASE_URL}${url}?t=${timestamp}`;
        }
        return `${API_BASE_URL}/${url}?t=${timestamp}`;
    };

    // ✅ 이미지 기반 상품 검색 (쿼리 직접 전달 방식)
    const searchProductsByImage = useCallback(async (imageBase64: string, targetQuery: string, target: string = "full") => {
        setIsSearchingProducts(true);
        try {
            const clipResponse = await client.post('/search/search-by-clip', {
                image_b64: imageBase64,
                limit: 12,
                query: targetQuery, // ✅ 상태값이 아닌 인자값 사용
                target: target
            });
            
            if (clipResponse.data && clipResponse.data.products) {
                setResults(clipResponse.data.products);
                setTimestamp(Date.now());
            }
        } catch (error) {
            console.error("Image-based search failed:", error);
        } finally {
            setIsSearchingProducts(false);
        }
    }, []);

    // [핵심] 검색 로직
    const handleSearch = useCallback(async (currentQuery: string, currentImage: File | null, isVoice: boolean = false) => {
        if (!currentQuery && !currentImage) return;
        
        // 초기화
        if (currentQuery) addRecentSearch(currentQuery);
        setIsLoading(true);
        setResults([]);
        setAiAnalysis(null);
        setSelectedImage(null);
        setCurrentText("");
        setShowProducts(false);
        setTimestamp(Date.now());
        
        // ✅ 원본 검색어 상태 업데이트 (UI용)
        setOriginalQuery(currentQuery);

        const formData = new FormData();
        formData.append('query', currentQuery);
        if (currentImage) formData.append('image_file', currentImage);
        formData.append('limit', '12');

        try {
            const response = await client.post<SearchResult>(API_ENDPOINT, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const data = response.data;
            setResults(data.products || []);
            
            if (data.ai_analysis && data.ai_analysis.reference_image) {
                setAiAnalysis(data.ai_analysis);
                setSelectedImage(data.ai_analysis.reference_image);
                setCurrentText(data.ai_analysis.summary);
                
                if (isVoice) speak(data.ai_analysis.summary);
            } else {
                setShowProducts(true);
            }

        } catch (error: any) {
            console.error("Search failed:", error);
        } finally {
            setIsLoading(false);
        }
    }, [speak, addRecentSearch]);

    // 후보 이미지 선택 시 상품 재검색
    const handleSelectCandidateImage = async (imageBase64: string) => {
        setSelectedImage(imageBase64);
        
        if (showProducts) {
            // ✅ originalQuery 상태값 사용 (렌더링 이후라 안전)
            await searchProductsByImage(imageBase64, originalQuery, "full");
        }
    };

    const handleAnalyzeSelectedImage = async () => {
        if (!selectedImage || !query) return;
        setIsAnalyzingImage(true);
        try {
            const response = await client.post('/search/analyze-image', {
                image_b64: selectedImage,
                query: query
            });
            setCurrentText(response.data.analysis);
        } catch (e) {
            console.error(e);
            setCurrentText("상세 분석에 실패했습니다. 잠시 후 다시 시도해주세요.");
        } finally {
            setIsAnalyzingImage(false);
        }
    };

    // ✅ 상품 보기 핸들러들
    const handleShowProducts = async () => {
        setShowProducts(true);
        if (selectedImage) {
            await searchProductsByImage(selectedImage, originalQuery, "full");
        }
        setTimeout(() => productSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    };

    const handleShowUpperOnly = async () => {
        setShowProducts(true);
        if (selectedImage) {
            await searchProductsByImage(selectedImage, originalQuery, "upper");
        }
        setTimeout(() => productSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    };

    const handleShowLowerOnly = async () => {
        setShowProducts(true);
        if (selectedImage) {
            await searchProductsByImage(selectedImage, originalQuery, "lower");
        }
        setTimeout(() => productSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    };

    const handleScrollTop = () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const handleVoiceSearch = () => {
        if (!('webkitSpeechRecognition' in window)) {
            alert('Chrome 브라우저를 사용해주세요.');
            return;
        }
        const recognition = new (window as any).webkitSpeechRecognition();
        recognition.lang = 'ko-KR';
        recognition.onstart = () => speak("듣고 있습니다.");
        recognition.onresult = (event: any) => {
            const transcript = event.results[0][0].transcript;
            setQuery(transcript);
            handleSearch(transcript, imageFile, true); 
        };
        recognition.start();
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        handleSearch(query, imageFile, false);
    };

    const previewUrl = imageFile ? URL.createObjectURL(imageFile) : null;

    useEffect(() => {
        if (queryTextFromUrl) {
            setQuery(queryTextFromUrl);
            handleSearch(queryTextFromUrl, null, false);
        }
    }, [queryTextFromUrl, handleSearch]);

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-8 pb-40">
            {/* 헤더 & 검색바 */}
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-8 h-8 text-purple-600" /> AI 통합 검색
            </h1>

            <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-lg p-6 border border-gray-100 transition-shadow hover:shadow-xl">
                <div className="flex items-center space-x-3 mb-4">
                    <SearchIcon className="w-6 h-6 text-gray-400" />
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="예: 장원영 공항 패션, 시사회 룩..."
                        className="flex-1 text-xl border-none focus:ring-0 outline-none placeholder:text-gray-300 font-medium"
                    />
                    <button type="button" onClick={handleVoiceSearch} className="p-3 rounded-full hover:bg-purple-50 transition-colors">
                        <Mic className="w-6 h-6 text-purple-500" />
                    </button>
                    <button type="submit" disabled={isLoading} className="px-8 py-3 bg-purple-600 text-white rounded-xl font-bold hover:bg-purple-700 transition-all active:scale-95">
                        검색
                    </button>
                </div>
                {!isLoading && (
                    <div {...(imageFile ? {} : {onClick: () => fileInputRef.current?.click()})} className="cursor-pointer">
                         <input type="file" accept="image/*" ref={fileInputRef} onChange={handleFileChange} className="hidden" />
                         {imageFile ? (
                             <div className="mt-2 flex items-center gap-2 bg-purple-50 p-2 rounded-lg w-fit animate-in fade-in">
                                <img src={previewUrl || ''} className="w-10 h-10 rounded object-cover" alt="preview"/>
                                <span className="text-sm text-purple-700 font-medium">{imageFile.name}</span>
                                <X className="w-4 h-4 cursor-pointer hover:text-red-500" onClick={(e) => {e.stopPropagation(); setImageFile(null)}}/>
                             </div>
                         ) : (
                             <p className="text-xs text-gray-400 text-center mt-2 hover:text-purple-500 transition-colors">이미지를 드래그하거나 클릭하여 업로드</p>
                         )}
                    </div>
                )}
            </form>

            {/* 로딩 애니메이션 */}
            {isLoading && (
                <div className="flex flex-col items-center py-24 animate-in fade-in duration-500">
                    <div className="relative">
                        <div className="absolute inset-0 bg-purple-200 rounded-full animate-ping opacity-75"></div>
                        <div className="relative bg-white p-6 rounded-full shadow-lg border border-purple-100">
                            <span className="text-5xl animate-bounce">{LOADING_STEPS[loadingStepIndex].icon}</span>
                        </div>
                    </div>
                    <h3 className="mt-8 text-xl font-bold text-gray-800 transition-all duration-300 min-h-[28px] text-center">
                        {LOADING_STEPS[loadingStepIndex].text}
                    </h3>
                </div>
            )}

            {/* [1단계] Visual RAG 리포트 */}
            {!isLoading && aiAnalysis && (
                <div className="mb-12 bg-white rounded-2xl p-6 border border-gray-100 shadow-sm animate-in zoom-in-95 duration-500 overflow-hidden">
                    <div className="flex flex-col md:flex-row gap-8 items-start">
                        {/* 이미지 & 후보군 */}
                        <div className="w-full md:w-1/3 flex-shrink-0 flex flex-col gap-4">
                            <div className="relative rounded-xl overflow-hidden bg-gray-100 shadow-md group aspect-[3/4]">
                                <img 
                                    src={getBustedImage(selectedImage || aiAnalysis.reference_image || '')} 
                                    alt="Trend Ref" 
                                    referrerPolicy="no-referrer"
                                    className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500" 
                                />
                                <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-sm text-white text-xs px-3 py-1.5 rounded-full flex gap-1.5 items-center">
                                    <TrendingUp className="w-3 h-3" /> Trend Reference
                                </div>
                            </div>
                            
                            {aiAnalysis.candidates && aiAnalysis.candidates.length > 0 && (
                                <div className="animate-in slide-in-from-bottom-2 fade-in">
                                    <p className="text-xs text-gray-500 mb-2 font-medium ml-1 flex items-center gap-1">
                                        <ImageIcon className="w-3 h-3"/> 다른 스타일 보기 (클릭하면 상품 재검색)
                                    </p>
                                    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide snap-x">
                                        {aiAnalysis.candidates.map((cand, idx) => (
                                            <button 
                                                key={idx}
                                                onClick={() => handleSelectCandidateImage(cand.image_base64)}
                                                className={`relative w-16 h-20 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-all snap-start ${
                                                    selectedImage === cand.image_base64 
                                                    ? 'border-purple-600 ring-2 ring-purple-100 scale-105' 
                                                    : 'border-transparent hover:border-gray-300 opacity-80 hover:opacity-100'
                                                }`}
                                            >
                                                <img 
                                                    src={getBustedImage(cand.image_base64)} 
                                                    referrerPolicy="no-referrer"
                                                    className="w-full h-full object-cover" 
                                                    alt={`candidate ${idx}`} 
                                                />
                                                <div className="absolute bottom-0 w-full bg-black/50 text-[9px] text-white text-center py-0.5">
                                                    {cand.score}%
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 텍스트 & 액션 버튼 */}
                        <div className="flex-1 py-2 space-y-6 min-w-0">
                            <div className="bg-purple-50/50 rounded-2xl p-6 md:p-8 border border-purple-100 relative shadow-sm min-h-[300px] overflow-hidden">
                                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                                    <div className="flex items-center gap-2">
                                        <Sparkles className="w-5 h-5 text-purple-600" />
                                        <h2 className="text-lg font-bold text-gray-800">스타일 분석 리포트</h2>
                                    </div>
                                    
                                    {selectedImage && selectedImage !== aiAnalysis.reference_image && (
                                        <button 
                                            onClick={handleAnalyzeSelectedImage}
                                            disabled={isAnalyzingImage}
                                            className="text-xs bg-white border border-purple-200 text-purple-700 px-3 py-1.5 rounded-full hover:bg-purple-50 transition-colors flex items-center gap-1 shadow-sm"
                                        >
                                            {isAnalyzingImage ? <RefreshCw className="w-3 h-3 animate-spin"/> : <Sparkles className="w-3 h-3"/>}
                                            {isAnalyzingImage ? "분석 중..." : "이 스타일 상세 분석하기"}
                                        </button>
                                    )}
                                </div>

                                {isAnalyzingImage ? (
                                    <div className="flex flex-col items-center justify-center h-40 space-y-3 opacity-70">
                                        <RefreshCw className="w-8 h-8 text-purple-500 animate-spin" />
                                        <p className="text-sm text-purple-700 font-medium">AI가 새로운 스타일을 분석하고 있습니다...</p>
                                    </div>
                                ) : (
                                    <div className="prose prose-purple max-w-none animate-in fade-in duration-300 overflow-hidden">
                                        <p className="text-gray-800 leading-relaxed text-base whitespace-pre-wrap break-words overflow-wrap-anywhere font-medium">
                                            {currentText}
                                        </p>
                                    </div>
                                )}
                            </div>

                            <div className="space-y-4 animate-in slide-in-from-bottom-4 fade-in">
                                <div className="bg-white border border-gray-200 rounded-tr-2xl rounded-br-2xl rounded-bl-2xl p-4 shadow-sm inline-block relative max-w-full">
                                    <p className="text-gray-800 font-medium">
                                        분석된 스타일과 유사한 상품을 찾아드릴까요?
                                    </p>
                                    <div className="absolute top-0 -left-2 w-4 h-4 bg-white border-l border-b border-gray-200 transform rotate-45"></div>
                                </div>
                                
                                <div className="flex flex-wrap gap-3">
                                    <button 
                                        onClick={handleShowProducts}
                                        disabled={isSearchingProducts}
                                        className="px-6 py-3 bg-indigo-600 text-white rounded-full font-bold hover:bg-indigo-700 transition-all flex items-center gap-2 shadow-md hover:shadow-lg active:scale-95 disabled:opacity-50"
                                    >
                                        {isSearchingProducts ? (
                                            <>
                                                <RefreshCw className="w-5 h-5 animate-spin" /> 검색 중...
                                            </>
                                        ) : (
                                            <>
                                                <Check className="w-5 h-5" /> 네, 전체 코디 보여줘
                                            </>
                                        )}
                                    </button>
                                    <button 
                                        onClick={handleShowUpperOnly}
                                        disabled={isSearchingProducts}
                                        className="px-5 py-3 bg-white border border-gray-200 text-gray-600 rounded-full font-medium hover:bg-purple-50 hover:border-purple-300 hover:text-purple-700 transition-all disabled:opacity-50"
                                    >
                                        👕 상의만
                                    </button>
                                    <button 
                                        onClick={handleShowLowerOnly}
                                        disabled={isSearchingProducts}
                                        className="px-5 py-3 bg-white border border-gray-200 text-gray-600 rounded-full font-medium hover:bg-purple-50 hover:border-purple-300 hover:text-purple-700 transition-all disabled:opacity-50"
                                    >
                                        👖 하의만
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* [2단계] 상품 리스트 */}
            {!isLoading && showProducts && results.length > 0 && (
                <div ref={productSectionRef} className="animate-in slide-in-from-bottom-10 duration-700 fade-in space-y-8 pt-8 border-t border-gray-100">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <ShoppingBag className="w-6 h-6 text-gray-700" />
                            <h2 className="text-2xl font-bold text-gray-900">추천 상품 ({results.length})</h2>
                            {isSearchingProducts && (
                                <RefreshCw className="w-5 h-5 text-purple-500 animate-spin ml-2" />
                            )}
                        </div>
                        <button onClick={handleScrollTop} className="text-gray-500 hover:text-purple-600 flex items-center gap-1 text-sm font-medium transition-colors">
                            <ArrowUp className="w-4 h-4" /> 분석 다시 보기
                        </button>
                      </div>

                      <div className="bg-gray-50 rounded-3xl p-8 border border-gray-100">
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                            {results.map((product) => (
                                <ProductCard 
                                    key={`${product.id}-${timestamp}`} 
                                    product={{
                                        ...product,
                                        image_url: getBustedImage(product.image_url)
                                    }} 
                                /> 
                            ))}
                        </div>
                    </div>
                </div>
            )}
            
            {/* 결과 없음 */}
            {!isLoading && showProducts && results.length === 0 && (
                <div className="text-center py-32 text-gray-500 animate-in fade-in flex flex-col items-center">
                    <AlertCircle className="w-16 h-16 text-gray-300 mb-4" />
                    <p className="text-xl mb-4 font-medium text-gray-600">
                        {aiAnalysis ? "분석한 스타일과 일치하는 상품 재고가 없습니다." : "검색 결과가 없습니다."}
                    </p>
                    <button onClick={() => setQuery('')} className="text-purple-600 font-medium hover:underline bg-purple-50 px-6 py-2 rounded-full">
                        다른 키워드로 검색해보세요
                    </button>
                </div>
            )}

            <style>{`
                .overflow-wrap-anywhere {
                    overflow-wrap: anywhere;
                    word-break: break-word;
                }
            `}</style>
        </div>
    );
}