import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, ShoppingCart } from 'lucide-react';
import { getImageUrl } from '../../utils/imageUtils';

// 백엔드 스키마와 일치하는 타입 정의
export interface ProductResponse {
    id: number;
    name: string;
    description: string;
    price: number;
    stock_quantity: number;
    category: string;
    image_url: string;
    in_stock: boolean;
}

interface ProductCardProps {
    product: ProductResponse;
}

export default function ProductCard({ product }: ProductCardProps) {
    const [isLiked, setIsLiked] = useState(false);
    
    // ✅ FIX: 이미지 URL 변환 유틸리티 사용
    const displayImage = getImageUrl(product.image_url);
        
    const formattedPrice = new Intl.NumberFormat('ko-KR').format(product.price);

    // 상세 페이지 경로 (App.tsx의 라우트 설정과 일치해야 함)
    const detailPath = `/products/${product.id}`;

    return (
        <div className="group relative flex flex-col w-full min-w-[200px] overflow-hidden">
            {/* 1. 이미지 영역 (클릭 시 상세 이동) */}
            <Link 
                to={detailPath}
                className="relative aspect-[3/4] overflow-hidden rounded-2xl bg-gray-100 shadow-sm hover:shadow-md transition-all duration-300 block"
            >
                <img
                    src={displayImage}
                    alt={product.name}
                    loading="lazy"
                    decoding="async"
                    className="h-full w-full object-cover object-center transition-transform duration-700 group-hover:scale-110"
                    onError={(e) => {
                        e.currentTarget.src = "https://placehold.co/400x500/CCCCCC/666666?text=No+Image";
                    }}
                />
                
                {/* 품절 오버레이 */}
                {!product.in_stock && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <span className="text-white font-bold px-3 py-1 border-2 border-white rounded-md">SOLD OUT</span>
                    </div>
                )}

                {/* 호버 시 나타나는 '장바구니 담기' 버튼 */}
                <div className="absolute inset-x-0 bottom-0 p-4 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out z-10">
                    <button 
                        className="w-full py-3 bg-white/95 backdrop-blur-sm text-sm font-bold text-gray-900 rounded-xl shadow-lg hover:bg-purple-600 hover:text-white transition-all flex items-center justify-center gap-2"
                        onClick={(e) => {
                            e.preventDefault(); // 상세 이동 방지
                            alert(`${product.name}을(를) 장바구니에 담았습니다!`);
                        }}
                    >
                        <ShoppingCart size={16} />
                        담기
                    </button>
                </div>
            </Link>

            {/* 2. 상품 정보 영역 */}
            <div className="mt-3 flex justify-between items-start px-1">
                <Link to={detailPath} className="flex-1 pr-2 group-hover:text-purple-700 transition-colors">
                    <p className="text-xs font-bold text-purple-600 mb-1 uppercase tracking-wider">
                        {product.category || "ITEM"} 
                    </p>
                    <h3 className="text-base font-semibold text-gray-900 line-clamp-1 mb-1 leading-snug">
                        {product.name}
                    </h3>
                    <p className="text-lg font-bold text-gray-900">
                        {formattedPrice}원
                    </p>
                </Link>

                {/* 찜하기 버튼 */}
                <button
                    onClick={(e) => {
                        e.preventDefault();
                        setIsLiked(!isLiked);
                    }}
                    className="shrink-0 p-2 -mr-2 rounded-full hover:bg-gray-50 transition-colors"
                >
                    <Heart 
                        size={22} 
                        className={`transition-all duration-300 ${isLiked ? 'fill-red-500 text-red-500 scale-110' : 'text-gray-300 hover:text-gray-400'}`} 
                    />
                </button>
            </div>
        </div>
    );
}