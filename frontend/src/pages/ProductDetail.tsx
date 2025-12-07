import React, { useState, useCallback, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Loader2, Zap, Heart, MessageSquare, Send, Maximize2, ArrowLeft, ShoppingBag } from 'lucide-react';

// [중요] 실제 API 클라이언트와 컴포넌트를 import 합니다.
import client from '../api/client';
import ProductCard from '../components/product/ProductCard';
import Modal from '../components/ui/Modal';

// --- Types ---
interface ProductResponse {
    id: number;
    name: string;
    description: string;
    price: number;
    stock_quantity: number;
    category: string;
    image_url: string;
    in_stock: boolean;
}

interface CoordinationResponse {
    answer: string;
    products: ProductResponse[];
}

interface LLMQueryResponse {
    answer: string;
}

// LLM 질문 훅 (실제 API 호출)
const useLLMQuery = (productId: number) => {
    return useMutation<LLMQueryResponse, Error, string>({
        mutationFn: async (question: string) => {
            const res = await client.post(`/products/${productId}/llm-query`, { question });
            return res.data;
        },
    });
};

export default function ProductDetail() {
    // 1. URL에서 상품 ID 가져오기 (문자열 -> 숫자 변환)
    const { id } = useParams<{ id: string }>();
    const productId = Number(id);

    // 2. 상품 데이터 상태
    const [product, setProduct] = useState<ProductResponse | null>(null);
    const [isProductLoading, setIsProductLoading] = useState(true);
    const [isProductError, setIsProductError] = useState(false);

    // 3. 실제 서버에서 상품 정보 가져오기
    useEffect(() => {
        const fetchProduct = async () => {
            if (!productId) return;
            setIsProductLoading(true);
            try {
                // [핵심 수정] URL의 productId를 사용하여 실제 데이터를 요청합니다.
                const response = await client.get(`/products/${productId}`);
                setProduct(response.data);
            } catch (err) {
                console.error("Failed to fetch product:", err);
                setIsProductError(true);
            } finally {
                setIsProductLoading(false);
            }
        };
        fetchProduct();
    }, [productId]); // ID가 바뀌면 다시 호출

    // AI 코디 관련 상태
    const [coordinationResult, setCoordinationResult] = useState<CoordinationResponse | null>(null);
    const [isCoordinationLoading, setIsCoordinationLoading] = useState(false);

    // LLM 질문 상태
    const [currentQuestion, setCurrentQuestion] = useState('');
    const [qaHistory, setQaHistory] = useState<Array<{ type: 'user' | 'ai', text: string }>>([]);
    
    const llmQueryMutation = useLLMQuery(productId || 0);

    // UI 상태
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [modalContent, setModalContent] = useState<React.ReactNode>(null);
    const [modalTitle, setModalTitle] = useState('');
    const [isWished, setIsWished] = useState(false);

    // --- 핸들러 ---

    // AI 코디 추천 (실제 API 호출)
    const handleAICoordination = useCallback(async () => {
        if (!product) return;
        setIsCoordinationLoading(true);
        setCoordinationResult(null);

        try {
            const res = await client.get(`/products/ai-coordination/${product.id}`); 
            const apiResponse = res.data;
            setCoordinationResult(apiResponse);
            
            setModalTitle("✨ AI 스타일리스트 추천 코디");
            setModalContent(
                <div className="space-y-6">
                    <div className="bg-purple-50 p-5 rounded-xl border border-purple-100">
                        <div className="flex items-start gap-3">
                            <Zap className="w-5 h-5 text-purple-600 mt-1 shrink-0" />
                            <p className="text-gray-800 font-medium whitespace-pre-wrap leading-relaxed text-sm">
                                {apiResponse.answer}
                            </p>
                        </div>
                    </div>
                    <div>
                        <h4 className="text-xs font-bold text-gray-500 mb-3 uppercase tracking-wider flex items-center gap-2">
                            <ShoppingBag className="w-4 h-4" /> 함께 입으면 좋은 아이템
                        </h4>
                        {apiResponse.products.length > 0 ? (
                            <div className="grid grid-cols-2 gap-4">
                                {apiResponse.products.map(p => (
                                    <ProductCard key={p.id} product={p} />
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 bg-gray-50 rounded-xl text-gray-400 text-sm">
                                추천 상품을 찾지 못했습니다.
                            </div>
                        )}
                    </div>
                </div>
            );
            setIsModalOpen(true);

        } catch (e) {
            alert('AI 코디 분석 중 오류가 발생했습니다.');
            console.error("AI Coordination Error:", e);
        } finally {
            setIsCoordinationLoading(false);
        }
    }, [product]);

    // LLM 질문 제출
    const handleLLMSubmit = () => {
        const trimmedQuestion = currentQuestion.trim();
        if (!trimmedQuestion || llmQueryMutation.isPending) return;

        setQaHistory(prev => [...prev, { type: 'user', text: trimmedQuestion }]);
        setCurrentQuestion('');

        llmQueryMutation.mutate(trimmedQuestion, {
            onSuccess: (data) => {
                setQaHistory(prev => [...prev, { type: 'ai', text: data.answer }]);
            },
            onError: () => {
                setQaHistory(prev => [...prev, { type: 'ai', text: "죄송합니다. AI 서비스 연결이 원활하지 않습니다." }]);
            }
        });
    };

    const handleAddToCart = () => alert(`🛒 ${product?.name} 장바구니에 담기 성공!`);
    const handleToggleWishlist = () => {
        setIsWished(prev => !prev);
        alert(`💖 위시리스트 ${!isWished ? '추가' : '제거'} 완료`);
    };

    // 로딩 및 에러 화면
    if (isProductLoading) return <div className="h-screen flex items-center justify-center"><Loader2 className="w-10 h-10 animate-spin text-purple-600" /></div>;
    if (isProductError || !product) return (
        <div className="h-screen flex flex-col items-center justify-center text-gray-500 gap-4">
            <p>상품 정보를 불러올 수 없습니다.</p>
            <Link to="/" className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black">메인으로 돌아가기</Link>
        </div>
    );

    const defaultAIBriefing = product.description || "AI가 상품 상세 정보를 분석하고 있습니다...";

    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in pb-24">
            {/* 뒤로가기 헤더 */}
            <div className="mb-6">
                <Link to="/" className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm font-medium">
                    <ArrowLeft className="w-4 h-4 mr-1" /> 목록으로 돌아가기
                </Link>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 mb-16">
                {/* 이미지 섹션 */}
                <div className="relative bg-gray-100 rounded-3xl overflow-hidden aspect-[3/4] lg:aspect-square shadow-sm group">
                    <img 
                        src={product.image_url || "/placeholder.png"} 
                        alt={product.name} 
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                        onError={(e) => (e.currentTarget.src = "/placeholder.png")}
                    />
                    <button className="absolute top-4 right-4 p-3 bg-white/80 backdrop-blur-md rounded-full text-gray-700 hover:bg-white hover:text-purple-600 transition-all shadow-sm">
                        <Maximize2 className="w-5 h-5" />
                    </button>
                </div>

                {/* 정보 섹션 */}
                <div className="flex flex-col justify-center">
                    <div>
                        <div className="flex items-center gap-2 mb-4">
                            <span className="px-3 py-1 bg-purple-100 text-purple-700 text-xs font-bold rounded-full uppercase tracking-wide">
                                {product.category}
                            </span>
                            {product.in_stock ? (
                                <span className="text-xs font-medium text-green-600 flex items-center gap-1 bg-green-50 px-2 py-1 rounded-full border border-green-100">
                                    <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div> 재고 보유
                                </span>
                            ) : (
                                <span className="text-xs font-medium text-red-500 bg-red-50 px-2 py-1 rounded-full border border-red-100">일시 품절</span>
                            )}
                        </div>
                        
                        <h1 className="text-3xl lg:text-4xl font-bold text-gray-900 leading-tight mb-4">{product.name}</h1>
                        <p className="text-3xl font-bold text-gray-900 mb-8 flex items-baseline gap-1">
                            {product.price.toLocaleString()}
                            <span className="text-lg font-normal text-gray-500">원</span>
                        </p>
                    </div>

                    {/* 액션 버튼 */}
                    <div className="flex gap-3 mb-8">
                        <button 
                            onClick={handleAddToCart}
                            className="flex-1 py-4 bg-gray-900 text-white font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-black transition-all shadow-lg active:scale-95"
                        >
                            <ShoppingBag className="w-5 h-5" /> 장바구니 담기
                        </button>
                        <button 
                            onClick={handleToggleWishlist}
                            className={`p-4 border rounded-xl transition-all active:scale-95 ${isWished ? 'border-red-200 bg-red-50 text-red-500' : 'border-gray-200 hover:bg-gray-50 text-gray-600'}`}
                        >
                            <Heart className={`w-6 h-6 ${isWished ? 'fill-current' : ''}`} />
                        </button>
                    </div>

                    {/* AI 기능 섹션 */}
                    <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl p-6 border border-purple-100 relative overflow-hidden">
                         <div className="absolute top-0 right-0 p-4 opacity-10">
                            <Zap className="w-24 h-24 text-purple-600" />
                        </div>
                        <h3 className="text-sm font-bold text-gray-900 mb-4 flex items-center gap-2 relative z-10">
                            <Zap className="w-4 h-4 text-purple-600" /> AI 스마트 쇼핑 어시스턴트
                        </h3>
                        <div className="flex flex-wrap gap-2 relative z-10">
                            <button 
                                onClick={handleAICoordination} 
                                disabled={isCoordinationLoading}
                                className="flex items-center gap-2 px-5 py-3 bg-white text-purple-700 text-sm font-bold rounded-xl shadow-sm hover:shadow-md border border-purple-100 transition-all disabled:opacity-70"
                            >
                                {isCoordinationLoading ? <Loader2 className='w-4 h-4 animate-spin' /> : "✨ 이 옷과 어울리는 코디 추천"}
                            </button>
                            <button className="px-4 py-3 bg-white text-gray-600 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors">
                                📏 사이즈 추천
                            </button>
                        </div>
                    </div>
                    
                    <div className="mt-8 prose prose-sm text-gray-600 border-t border-gray-100 pt-6">
                        <p>{product.description}</p>
                    </div>
                </div>
            </div>

            {/* AI 채팅 섹션 */}
            <div className="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-hidden ring-1 ring-black/5">
                <div className="p-6 bg-gray-50 border-b border-gray-100 flex justify-between items-center">
                    <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <div className="p-2 bg-indigo-600 rounded-lg text-white shadow-md">
                            <MessageSquare className="w-5 h-5" />
                        </div>
                        AI 스타일리스트에게 물어보세요
                    </h2>
                    <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-100">
                        BETA
                    </span>
                </div>
                
                <div className="flex flex-col lg:flex-row h-[600px] lg:h-[500px]">
                    {/* 왼쪽: AI 인사이트 */}
                    <div className="lg:w-1/3 p-6 border-b lg:border-b-0 lg:border-r border-gray-100 bg-gray-50/50 space-y-4 overflow-y-auto">
                        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                            <strong className="block text-indigo-600 mb-2 text-xs font-bold uppercase tracking-wider">Product Insight</strong> 
                            <p className="text-gray-700 text-sm leading-relaxed">{defaultAIBriefing}</p>
                        </div>
                        <div className="bg-blue-50 p-4 rounded-xl text-blue-800 text-xs font-medium border border-blue-100 flex items-start gap-2">
                             <span className="text-lg">💡</span>
                             <span>"이 옷 세탁은 어떻게 해?", "여름에 입기 더울까?" 처럼 궁금한 점을 자연스럽게 물어보세요.</span>
                        </div>
                    </div>

                    {/* 오른쪽: 채팅창 */}
                    <div className="flex-1 flex flex-col bg-white">
                        <div className="flex-1 overflow-y-auto p-6 space-y-4">
                            {qaHistory.length === 0 ? (
                                <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-3 opacity-60">
                                    <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                                        <MessageSquare className="w-8 h-8 text-gray-400" />
                                    </div>
                                    <p className="text-sm font-medium">궁금한 점을 입력하시면 AI가 즉시 답변해드립니다.</p>
                                </div>
                            ) : (
                                qaHistory.map((item, index) => (
                                    <div key={index} className={`flex ${item.type === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
                                        <div className={`max-w-[85%] px-5 py-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
                                            item.type === 'user' 
                                            ? 'bg-gray-900 text-white rounded-br-sm' 
                                            : 'bg-indigo-50 text-gray-800 rounded-tl-sm border border-indigo-100'
                                        }`}>
                                            {item.text}
                                        </div>
                                    </div>
                                ))
                            )}
                            {llmQueryMutation.isPending && (
                                <div className="flex justify-start animate-fade-in">
                                    <div className="bg-white border border-gray-100 px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-2">
                                        <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                                        <span className="text-xs text-gray-500 font-medium">AI가 답변 작성 중...</span>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="p-4 border-t border-gray-100 bg-gray-50">
                            <div className="flex gap-2 relative">
                                <input 
                                    type="text"
                                    value={currentQuestion}
                                    onChange={(e) => setCurrentQuestion(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleLLMSubmit()}
                                    disabled={llmQueryMutation.isPending}
                                    placeholder="상품에 대해 궁금한 점을 입력하세요..."
                                    className="flex-1 pl-5 pr-12 py-3.5 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all shadow-sm text-sm"
                                />
                                <button
                                    onClick={handleLLMSubmit}
                                    disabled={llmQueryMutation.isPending || !currentQuestion.trim()}
                                    className="absolute right-2 top-2 bottom-2 aspect-square bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center shadow-sm"
                                >
                                    <Send className="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={modalTitle} maxWidth="max-w-3xl">
                {modalContent}
            </Modal>
            <style>{`
                @keyframes fade-in {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-fade-in {
                    animation: fade-in 0.4s ease-out forwards;
                }
            `}</style>
        </div>
    );
}