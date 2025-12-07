import React, { useState, useCallback, useEffect } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { 
    Loader2, Zap, Heart, MessageSquare, Send, Maximize2, 
    ArrowLeft, ShoppingBag, CreditCard, CheckCircle, Ruler,
    User, X
} from 'lucide-react';

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
    gender?: string;
}

interface CoordinationResponse {
    answer: string;
    products: ProductResponse[];
}

interface LLMQueryResponse {
    answer: string;
}

interface BodyMeasurements {
    height: string;
    weight: string;
    chest: string;
    waist: string;
    hip: string;
    footSize: string;
    preferFit: 'tight' | 'regular' | 'loose';
}

// LLM 질문 훅
const useLLMQuery = (productId: number) => {
    return useMutation<LLMQueryResponse, Error, string>({
        mutationFn: async (question: string) => {
            const res = await client.post(`/products/${productId}/llm-query`, { question });
            return res.data;
        },
    });
};

export default function ProductDetail() {
    const { id } = useParams<{ id: string }>();
    const productId = Number(id);
    const navigate = useNavigate();
    const location = useLocation();

    // 상품 데이터 상태
    const [product, setProduct] = useState<ProductResponse | null>(null);
    const [isProductLoading, setIsProductLoading] = useState(true);
    const [isProductError, setIsProductError] = useState(false);

    // 상품 정보 가져오기
    useEffect(() => {
        const fetchProduct = async () => {
            if (!productId) return;
            setIsProductLoading(true);
            try {
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
    }, [productId]);

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
    
    // 장바구니 상태
    const [isInCart, setIsInCart] = useState(false);
    const [justAdded, setJustAdded] = useState(false);

    // ✅ 사이즈 추천 상태
    const [isSizeModalOpen, setIsSizeModalOpen] = useState(false);
    const [isSizeLoading, setIsSizeLoading] = useState(false);
    const [sizeRecommendation, setSizeRecommendation] = useState<string | null>(null);
    const [bodyMeasurements, setBodyMeasurements] = useState<BodyMeasurements>({
        height: '',
        weight: '',
        chest: '',
        waist: '',
        hip: '',
        footSize: '',
        preferFit: 'regular'
    });

    // 장바구니 상태 체크
    useEffect(() => {
        if (!product) return;
        const cart = JSON.parse(localStorage.getItem('cart') || '[]');
        const exists = cart.some((item: any) => item.id === product.id);
        setIsInCart(exists);
    }, [product]);

    // 위시리스트 상태 체크
    useEffect(() => {
        if (!product) return;
        const wishlist = JSON.parse(localStorage.getItem('wishlist') || '[]');
        setIsWished(wishlist.includes(product.id));
    }, [product]);

    // --- 핸들러 ---

    // 목록으로 돌아가기
    const handleGoBack = () => {
        if (window.history.length > 1) {
            navigate(-1);
        } else {
            navigate('/search');
        }
    };

    // 장바구니 담기
    const handleAddToCart = useCallback(async () => {
        if (!product) return;
        
        try {
            const cart = JSON.parse(localStorage.getItem('cart') || '[]');
            const existingIndex = cart.findIndex((item: any) => item.id === product.id);
            
            if (existingIndex > -1) {
                cart[existingIndex].quantity += 1;
            } else {
                cart.push({
                    id: product.id,
                    name: product.name,
                    price: product.price,
                    image_url: product.image_url,
                    quantity: 1
                });
            }
            
            localStorage.setItem('cart', JSON.stringify(cart));
            setIsInCart(true);
            setJustAdded(true);
            setTimeout(() => setJustAdded(false), 3000);
            
        } catch (error) {
            alert('장바구니 담기에 실패했습니다.');
        }
    }, [product]);

    const handleGoToCart = () => navigate('/cart');

    // 바로 구매하기
    const handleBuyNow = () => {
        if (!product) return;
        handleAddToCart();
        navigate('/checkout', { 
            state: { 
                directBuy: true,
                product: {
                    id: product.id,
                    name: product.name,
                    price: product.price,
                    image_url: product.image_url,
                    quantity: 1
                }
            } 
        });
    };

    // 위시리스트 토글
    const handleToggleWishlist = () => {
        if (!product) return;
        const wishlist = JSON.parse(localStorage.getItem('wishlist') || '[]');
        
        if (!isWished) {
            wishlist.push(product.id);
        } else {
            const index = wishlist.indexOf(product.id);
            if (index > -1) wishlist.splice(index, 1);
        }
        
        localStorage.setItem('wishlist', JSON.stringify(wishlist));
        setIsWished(!isWished);
    };

    // AI 코디 추천
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
                        {apiResponse.products && apiResponse.products.length > 0 ? (
                            <div className="grid grid-cols-2 gap-4">
                                {apiResponse.products.map((p: ProductResponse) => (
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

    // ✅ 사이즈 추천 핸들러
    const handleSizeRecommendation = async () => {
        if (!product) return;
        
        // 필수 입력 체크
        if (!bodyMeasurements.height || !bodyMeasurements.weight) {
            alert('키와 몸무게는 필수 입력 항목입니다.');
            return;
        }
        
        setIsSizeLoading(true);
        setSizeRecommendation(null);
        
        try {
            // AI 서비스에 사이즈 추천 요청
            const prompt = `
상품명: ${product.name}
카테고리: ${product.category}
성별: ${product.gender || 'Unisex'}

고객 체형 정보:
- 키: ${bodyMeasurements.height}cm
- 몸무게: ${bodyMeasurements.weight}kg
${bodyMeasurements.chest ? `- 가슴 둘레: ${bodyMeasurements.chest}cm` : ''}
${bodyMeasurements.waist ? `- 허리 둘레: ${bodyMeasurements.waist}cm` : ''}
${bodyMeasurements.hip ? `- 엉덩이 둘레: ${bodyMeasurements.hip}cm` : ''}
${bodyMeasurements.footSize ? `- 발 사이즈: ${bodyMeasurements.footSize}mm` : ''}
- 선호 핏: ${bodyMeasurements.preferFit === 'tight' ? '슬림핏' : bodyMeasurements.preferFit === 'loose' ? '오버핏' : '레귤러핏'}

위 정보를 바탕으로 이 상품의 적합한 사이즈를 추천해주세요.
추천 사이즈, 추천 이유, 핏 예상(슬림/적당/여유), 참고 사항을 포함해서 답변해주세요.
`;

            const res = await client.post(`/products/${product.id}/llm-query`, { question: prompt });
            setSizeRecommendation(res.data.answer);
            
        } catch (error) {
            console.error('Size recommendation error:', error);
            
            // Fallback: 간단한 로직으로 추천
            const height = parseInt(bodyMeasurements.height);
            const weight = parseInt(bodyMeasurements.weight);
            
            let recommendedSize = 'M';
            const bmi = weight / ((height / 100) ** 2);
            
            if (height < 165) {
                recommendedSize = bmi < 20 ? 'XS' : bmi < 23 ? 'S' : 'M';
            } else if (height < 175) {
                recommendedSize = bmi < 20 ? 'S' : bmi < 23 ? 'M' : bmi < 26 ? 'L' : 'XL';
            } else {
                recommendedSize = bmi < 20 ? 'M' : bmi < 23 ? 'L' : bmi < 26 ? 'XL' : 'XXL';
            }
            
            // 핏 선호도 반영
            if (bodyMeasurements.preferFit === 'tight') {
                const sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
                const currentIndex = sizes.indexOf(recommendedSize);
                if (currentIndex > 0) recommendedSize = sizes[currentIndex - 1];
            } else if (bodyMeasurements.preferFit === 'loose') {
                const sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
                const currentIndex = sizes.indexOf(recommendedSize);
                if (currentIndex < sizes.length - 1) recommendedSize = sizes[currentIndex + 1];
            }
            
            setSizeRecommendation(`
🎯 **추천 사이즈: ${recommendedSize}**

📏 **분석 결과**
- 키 ${height}cm, 몸무게 ${weight}kg 기준
- BMI: ${bmi.toFixed(1)}
- 선호 핏: ${bodyMeasurements.preferFit === 'tight' ? '슬림핏' : bodyMeasurements.preferFit === 'loose' ? '오버핏' : '레귤러핏'}

💡 **참고 사항**
- 브랜드별로 사이즈가 다를 수 있으니 상세 사이즈표를 확인해주세요.
- ${bodyMeasurements.preferFit === 'loose' ? '오버핏을 선호하시므로 한 사이즈 업을 고려했습니다.' : bodyMeasurements.preferFit === 'tight' ? '슬림핏을 선호하시므로 한 사이즈 다운을 고려했습니다.' : '레귤러핏 기준으로 추천드립니다.'}
            `);
        } finally {
            setIsSizeLoading(false);
        }
    };

    // 체형 정보 입력 핸들러
    const handleBodyChange = (field: keyof BodyMeasurements, value: string) => {
        setBodyMeasurements(prev => ({ ...prev, [field]: value }));
    };

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

    // 로딩 화면
    if (isProductLoading) {
        return (
            <div className="h-screen flex items-center justify-center">
                <Loader2 className="w-10 h-10 animate-spin text-purple-600" />
            </div>
        );
    }
    
    // 에러 화면
    if (isProductError || !product) {
        return (
            <div className="h-screen flex flex-col items-center justify-center text-gray-500 gap-4">
                <p>상품 정보를 불러올 수 없습니다.</p>
                <button 
                    onClick={() => navigate('/search')}
                    className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black"
                >
                    검색 페이지로 돌아가기
                </button>
            </div>
        );
    }

    const defaultAIBriefing = product.description || "AI가 상품 상세 정보를 분석하고 있습니다...";

    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in pb-24">
            {/* 뒤로가기 헤더 */}
            <div className="mb-6">
                <button 
                    onClick={handleGoBack}
                    className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm font-medium"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> 목록으로 돌아가기
                </button>
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
                    <div className="space-y-3 mb-8">
                        <div className="flex gap-3">
                            <button 
                                onClick={isInCart ? handleGoToCart : handleAddToCart}
                                disabled={!product.in_stock}
                                className={`flex-1 py-4 font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed ${
                                    isInCart 
                                        ? 'bg-green-600 text-white hover:bg-green-700' 
                                        : 'bg-gray-900 text-white hover:bg-black'
                                }`}
                            >
                                {isInCart ? (
                                    <>
                                        <CheckCircle className="w-5 h-5" /> 
                                        {justAdded ? '담겼습니다!' : '장바구니 보기'}
                                    </>
                                ) : (
                                    <>
                                        <ShoppingBag className="w-5 h-5" /> 장바구니 담기
                                    </>
                                )}
                            </button>
                            <button 
                                onClick={handleToggleWishlist}
                                className={`p-4 border rounded-xl transition-all active:scale-95 ${
                                    isWished 
                                        ? 'border-red-200 bg-red-50 text-red-500' 
                                        : 'border-gray-200 hover:bg-gray-50 text-gray-600'
                                }`}
                            >
                                <Heart className={`w-6 h-6 ${isWished ? 'fill-current' : ''}`} />
                            </button>
                        </div>

                        <button 
                            onClick={handleBuyNow}
                            disabled={!product.in_stock}
                            className="w-full py-4 bg-purple-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-purple-700 transition-all shadow-lg active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed"
                        >
                            <CreditCard className="w-5 h-5" /> 바로 구매하기
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
                            {/* ✅ 사이즈 추천 버튼 */}
                            <button 
                                onClick={() => setIsSizeModalOpen(true)}
                                className="flex items-center gap-2 px-4 py-3 bg-white text-gray-600 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors"
                            >
                                <Ruler className="w-4 h-4" /> 사이즈 추천
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
            
            {/* 코디 추천 모달 */}
            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={modalTitle} maxWidth="max-w-3xl">
                {modalContent}
            </Modal>

            {/* ✅ 사이즈 추천 모달 */}
            <Modal isOpen={isSizeModalOpen} onClose={() => setIsSizeModalOpen(false)} title="📏 AI 사이즈 추천" maxWidth="max-w-xl">
                <div className="space-y-6">
                    {!sizeRecommendation ? (
                        <>
                            <p className="text-sm text-gray-600">
                                체형 정보를 입력하시면 AI가 최적의 사이즈를 추천해드립니다.
                            </p>
                            
                            {/* 체형 입력 폼 */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        <User className="w-4 h-4 inline mr-1" /> 키 (cm) *
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.height}
                                        onChange={(e) => handleBodyChange('height', e.target.value)}
                                        placeholder="170"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        몸무게 (kg) *
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.weight}
                                        onChange={(e) => handleBodyChange('weight', e.target.value)}
                                        placeholder="65"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        가슴 둘레 (cm)
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.chest}
                                        onChange={(e) => handleBodyChange('chest', e.target.value)}
                                        placeholder="95"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        허리 둘레 (cm)
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.waist}
                                        onChange={(e) => handleBodyChange('waist', e.target.value)}
                                        placeholder="80"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        엉덩이 둘레 (cm)
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.hip}
                                        onChange={(e) => handleBodyChange('hip', e.target.value)}
                                        placeholder="95"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        발 사이즈 (mm)
                                    </label>
                                    <input 
                                        type="number"
                                        value={bodyMeasurements.footSize}
                                        onChange={(e) => handleBodyChange('footSize', e.target.value)}
                                        placeholder="265"
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                                    />
                                </div>
                            </div>
                            
                            {/* 핏 선호도 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    선호하는 핏
                                </label>
                                <div className="flex gap-3">
                                    {[
                                        { id: 'tight', label: '슬림핏', desc: '몸에 딱 맞게' },
                                        { id: 'regular', label: '레귤러', desc: '적당하게' },
                                        { id: 'loose', label: '오버핏', desc: '여유있게' },
                                    ].map((fit) => (
                                        <button
                                            key={fit.id}
                                            onClick={() => handleBodyChange('preferFit', fit.id as any)}
                                            className={`flex-1 p-3 rounded-xl border-2 transition-all text-center ${
                                                bodyMeasurements.preferFit === fit.id
                                                    ? 'border-purple-600 bg-purple-50'
                                                    : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        >
                                            <div className="font-medium text-gray-900">{fit.label}</div>
                                            <div className="text-xs text-gray-500">{fit.desc}</div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                            
                            <button 
                                onClick={handleSizeRecommendation}
                                disabled={isSizeLoading || !bodyMeasurements.height || !bodyMeasurements.weight}
                                className="w-full py-4 bg-purple-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-purple-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                            >
                                {isSizeLoading ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" /> AI가 분석 중...
                                    </>
                                ) : (
                                    <>
                                        <Ruler className="w-5 h-5" /> 사이즈 추천 받기
                                    </>
                                )}
                            </button>
                        </>
                    ) : (
                        /* 추천 결과 */
                        <div className="space-y-4">
                            <div className="bg-purple-50 p-5 rounded-xl border border-purple-100">
                                <div className="prose prose-sm text-gray-800 whitespace-pre-wrap">
                                    {sizeRecommendation}
                                </div>
                            </div>
                            <button 
                                onClick={() => {
                                    setSizeRecommendation(null);
                                    setBodyMeasurements({
                                        height: '',
                                        weight: '',
                                        chest: '',
                                        waist: '',
                                        hip: '',
                                        footSize: '',
                                        preferFit: 'regular'
                                    });
                                }}
                                className="w-full py-3 bg-gray-100 text-gray-700 font-medium rounded-xl hover:bg-gray-200 transition-colors"
                            >
                                다시 측정하기
                            </button>
                        </div>
                    )}
                </div>
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