import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
// 경로 재확인: 명시적 확장자 추가로 컴파일 오류 해결 시도
import client from '../api/client'; 
import { Loader2, Zap, Heart, MessageSquare, ShoppingCart, Send, Maximize2 } from 'lucide-react';
// 경로 재확인: 명시적 확장자 추가
import ProductCard from '../components/product/ProductCard'; 
// 경로 재확인: 명시적 확장자 추가
import Modal from '../components/ui/Modal'; 

// Mock Data Types (실제 스키마와 일치해야 합니다)
interface ProductResponse {
  id: number;
  name: string;
  description: string;
  price: number;
  stock_quantity: number;
  category: string;
  image_url: string;
  in_stock: boolean;
  created_at: string;
  updated_at: string;
}

interface CoordinationResponse {
    answer: string;
    products: ProductResponse[];
}

// --------------------------------------------------
// 1. 데이터 가져오기 (단일 상품)
// --------------------------------------------------
const useProductDetail = (productId: string | undefined) => {
  return useQuery<ProductResponse>({
    queryKey: ['productDetail', productId],
    queryFn: async () => {
      if (!productId) throw new Error("Product ID is missing.");
      // API 클라이언트 호출 경로는 이미 client.ts에 설정되어 있어야 함
      const res = await client.get(`/v1/products/${productId}`); 
      return res.data;
    },
    enabled: !!productId,
  });
};

// --------------------------------------------------
// 2. LLM 설명 요청 및 질문 답변
// --------------------------------------------------

interface LLMQueryResponse {
    answer: string;
}

// LLM 질문을 백엔드로 보내는 Mutation (상세 페이지 QA)
const useLLMQuery = (productId: number) => {
    return client.useMutation<LLMQueryResponse, Error, string>({
        mutationFn: async (question: string) => {
            const res = await client.post(`/v1/products/${productId}/llm-query`, { question });
            return res.data;
        },
    });
};


export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: product, isLoading: isProductLoading, isError: isProductError } = useProductDetail(id);
  
  // AI 코디 관련 상태
  const [coordinationResult, setCoordinationResult] = useState<CoordinationResponse | null>(null);
  const [isCoordinationLoading, setIsCoordinationLoading] = useState(false);

  // LLM 질문 상태
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [qaHistory, setQaHistory] = useState<Array<{ type: 'user' | 'ai', text: string }>>([]);
  const llmQueryMutation = useLLMQuery(product?.id || 0);

  // 모달 상태
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [modalContent, setModalContent] = useState<React.ReactNode>(null);


  // --------------------------------------------------
  // AI 기능 핸들러
  // --------------------------------------------------

  // AI 코디 추천 기능 (Feature 4)
  const handleAICoordination = useCallback(async () => {
    if (!product) return;
    setIsCoordinationLoading(true);
    setCoordinationResult(null);

    try {
        // ⭐ API 경로: products.py에 추가된 AI 코디 API 호출
        const res = await client.get(`/v1/products/ai-coordination/${product.id}`); 
        
        // 실제 API 응답 구조를 사용
        const apiResponse: CoordinationResponse = res.data;

        setCoordinationResult(apiResponse);
        
        // 추천 결과를 모달로 보여주기
        setModalTitle("AI 코디 추천 결과");
        setModalContent(
            <div className="space-y-4">
                <p className="text-gray-700 font-medium whitespace-pre-wrap">{apiResponse.answer}</p>
                <div className="grid grid-cols-2 gap-4">
                    {apiResponse.products.map(p => (
                        <ProductCard key={p.id} product={p} />
                    ))}
                </div>
            </div>
        );
        setIsModalOpen(true);

    } catch (e) {
        alert('AI 코디 추천에 실패했습니다. (백엔드 로그 확인 필요)');
        console.error(e);
    } finally {
        setIsCoordinationLoading(false);
    }
  }, [product]);

  // LLM 질문 제출 핸들러 (Feature 7)
  const handleLLMSubmit = () => {
    const trimmedQuestion = currentQuestion.trim();
    if (!trimmedQuestion || llmQueryMutation.isPending) return;

    // 1. QA 기록에 사용자 질문 추가
    setQaHistory(prev => [...prev, { type: 'user', text: trimmedQuestion }]);
    setCurrentQuestion('');

    // 2. LLM API 호출
    llmQueryMutation.mutate(trimmedQuestion, {
        onSuccess: (data) => {
            // 3. QA 기록에 AI 답변 추가
            setQaHistory(prev => [...prev, { type: 'ai', text: data.answer }]);
        },
        onError: (error) => {
            setQaHistory(prev => [...prev, { type: 'ai', text: "죄송합니다. LLM 서버와 통신 중 오류가 발생했습니다." }]);
            console.error(error);
        }
    });
  };
  
  // Enter 키 이벤트 핸들러
  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLLMSubmit();
    }
  };

  // --------------------------------------------------
  // 렌더링
  // --------------------------------------------------
  if (isProductLoading) {
    return <div className="text-center py-20"><Loader2 className="w-8 h-8 animate-spin mx-auto text-gray-500" /></div>;
  }
  if (isProductError || !product) {
    return <div className="text-center py-20 text-red-500">상품 정보를 불러올 수 없습니다.</div>;
  }

  // AI 생성 기본 설명 (Feature 7 상단)
  const defaultAIBriefing = product.description || "AI가 생성한 상세 설명이 곧 로드될 예정입니다.";

  // 비슷한 가격대 표시 로직 (Feature 3)
  const getMockPriceRange = (price: number) => {
      const min = Math.floor(price * 0.9 / 1000) * 1000;
      const max = Math.ceil(price * 1.1 / 1000) * 1000;
      return `${min.toLocaleString()}원 ~ ${max.toLocaleString()}원`;
  };


  return (
    <div className="max-w-6xl mx-auto p-4 md:p-8">
      {/* 상품 정보 영역 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
        
        {/* 이미지/갤러리 */}
        <div className="relative bg-gray-100 rounded-xl overflow-hidden aspect-square">
            <img 
                src={product.image_url || "/placeholder.png"} 
                alt={product.name} 
                className="w-full h-full object-cover"
                onError={(e) => (e.currentTarget.src = "/placeholder.png")}
            />
            <button className="absolute top-4 right-4 p-2 bg-white/50 backdrop-blur-sm rounded-full text-gray-700 hover:bg-white transition-colors shadow-md">
                <Maximize2 className="w-5 h-5" />
            </button>
        </div>

        {/* 상품 상세 */}
        <div className="space-y-6">
          <h1 className="text-3xl font-bold text-gray-900">{product.name}</h1>
          <p className="text-4xl font-extrabold text-black">{product.price.toLocaleString()}원</p>
          
          <div className="text-sm text-gray-600 space-y-2 border-t pt-4">
            <p><strong>카테고리:</strong> {product.category}</p>
            <p><strong>재고:</strong> {product.in_stock ? `${product.stock_quantity}개 재고 있음` : '품절'}</p>
            <p><strong>설명:</strong> {product.description.slice(0, 150)}...</p>
          </div>

          <div className="flex space-x-3 pt-4">
            <button className="flex-1 py-3 bg-black text-white font-bold rounded-lg flex items-center justify-center space-x-2 hover:bg-gray-800 transition-colors">
              <ShoppingCart className="w-5 h-5" />
              <span>장바구니 담기</span>
            </button>
            <button className="p-3 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors">
              <Heart className="w-5 h-5" />
            </button>
          </div>
          
          {/* AI 추천 버튼들 (Feature 3, 5, 6) */}
          <div className="flex flex-wrap gap-2 pt-4 border-t">
            <button 
                onClick={handleAICoordination} // Feature 4: AI 코디
                disabled={isCoordinationLoading}
                className="flex items-center space-x-1 px-4 py-2 bg-purple-500 text-white text-sm rounded-full shadow-md hover:bg-purple-600 transition-colors disabled:opacity-50"
            >
                <Zap className="w-4 h-4" />
                {isCoordinationLoading ? <Loader2 className='w-4 h-4 animate-spin' /> : 'AI 코디 추천'}
            </button>

            {/* Feature 3: 비슷한 가격 버튼 - 클릭 시 관련 API 호출 로직 추가 필요 */}
            <button className="btn-ai-small">
                비슷한 가격 ({getMockPriceRange(product.price)})
            </button>
            {/* Feature 5, 6: 비슷한 색상, 다른 브랜드 버튼 - 클릭 시 관련 API 호출 로직 추가 필요 */}
            <button className="btn-ai-small">
                비슷한 색상
            </button>
            <button className="btn-ai-small">
                다른 브랜드
            </button>
          </div>

        </div>
      </div>

      {/* LLM 상품 설명 및 Q&A 영역 (Feature 7) */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6 space-y-6">
        <h2 className="text-2xl font-bold text-black flex items-center space-x-2">
            <MessageSquare className="w-6 h-6 text-indigo-500" />
            <span>AI 스타일리스트에게 문의하기</span>
        </h2>
        
        {/* LLM 기본 설명 */}
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <strong className="text-indigo-600">AI 상품 설명:</strong> 
            <p className="mt-1 text-gray-700 whitespace-pre-wrap">{defaultAIBriefing}</p>
            <p className="mt-2 text-xs text-gray-500">
                추천 이유: 이 제품이 고객님의 관심사와 트렌드에 완벽하게 부합합니다.
            </p>
        </div>

        {/* Q&A 기록 */}
        <div className="h-64 overflow-y-auto space-y-4 p-2 bg-white border rounded-lg">
            {qaHistory.length === 0 ? (
                <p className="text-center text-gray-400 py-10">
                    상품의 재질, 착용 팁, 코디 등에 대해 질문해보세요.
                </p>
            ) : (
                qaHistory.map((item, index) => (
                    <div key={index} className={`flex ${item.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-xs md:max-w-md p-3 rounded-xl shadow-md ${
                            item.type === 'user' 
                            ? 'bg-blue-500 text-white rounded-br-none' 
                            : 'bg-gray-100 text-gray-800 rounded-tl-none'
                        }`}>
                            <p className="font-medium text-sm">{item.text}</p>
                        </div>
                    </div>
                ))
            )}
            {/* 로딩 인디케이터 */}
            {llmQueryMutation.isPending && (
                 <div className="flex justify-start">
                    <div className="max-w-xs md:max-w-md p-3 rounded-xl bg-gray-100 text-gray-800 rounded-tl-none flex items-center space-x-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <p className="text-sm">AI가 답변을 생성 중입니다...</p>
                    </div>
                </div>
            )}
        </div>

        {/* 질문 입력 폼 */}
        <div className="flex space-x-3">
          <input 
            type="text"
            value={currentQuestion}
            onChange={(e) => setCurrentQuestion(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={llmQueryMutation.isPending}
            placeholder="예: 이 코트의 보온성은 어떤가요?"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
          />
          <button
            onClick={handleLLMSubmit}
            disabled={llmQueryMutation.isPending || !currentQuestion.trim()}
            className="p-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
      
      {/* 코디 추천 모달 */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={modalTitle} maxWidth="max-w-2xl">
        {modalContent}
      </Modal>

      {/* 스타일링을 위한 임시 CSS 클래스 */}
      <style>{`
          .btn-ai-small {
              @apply px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-full hover:bg-gray-200 transition-colors;
          }
      `}</style>

    </div>
  );
}