import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, ShoppingCart } from 'lucide-react';

// Mock ProductResponse (실제 types/index.ts에 정의되어야 함)
// 백엔드 스키마 ProductResponse와 일치하는 기본 타입입니다.
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

interface ProductCardProps {
    product: ProductResponse;
}

export default function ProductCard({ 
    product
}: ProductCardProps) {
    const [isLiked, setIsLiked] = useState(false);
    
    const displayImage = product.image_url || 'https://placehold.co/400x500/e2e8f0/64748b?text=No+Image';
    const formattedPrice = new Intl.NumberFormat('ko-KR').format(product.price);

    return (
        <div className="group relative flex flex-col w-full min-w-[200px] max-w-[280px]">
            {/* 1. 이미지 영역 (링크 포함) */}
            <Link 
                to={`/products/${product.id}`} 
                className="relative aspect-[3/4] overflow-hidden rounded-xl bg-gray-100 dark:bg-gray-800 shadow-md"
            >
                <img
                    src={displayImage}
                    alt={product.name}
                    loading="lazy" 
                    decoding="async"
                    className="h-full w-full object-cover object-center transition-transform duration-500 group-hover:scale-105"
                    onError={(e) => {
                        e.currentTarget.src = "https://placehold.co/400x500/CCCCCC/666666?text=No+Image";
                    }}
                />
                
                {/* 호버 시 나타나는 '장바구니 담기' 버튼 (Overlay) */}
                <div className="absolute inset-x-0 bottom-0 p-4 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out">
                    <button 
                        className="w-full py-3 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm text-sm font-bold text-gray-900 dark:text-white rounded-lg shadow-lg hover:bg-purple-600 hover:text-white dark:hover:bg-purple-600 transition-colors flex items-center justify-center gap-2"
                        onClick={(e) => {
                            e.preventDefault(); 
                            // 장바구니 추가 API 호출 로직 (생략)
                            alert(`상품 ID ${product.id} 장바구니 담기`);
                        }}
                    >
                        <ShoppingCart size={16} />
                        담기
                    </button>
                </div>
            </Link>

            {/* 2. 상품 정보 영역 */}
            <div className="mt-2 flex justify-between items-start">
                <Link to={`/products/${product.id}`} className="flex-1 pr-2">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        {product.category || "카테고리"} 
                    </p>
                    <h3 className="text-sm font-medium text-gray-900 dark:text-white line-clamp-2 leading-tight group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                        {product.name}
                    </h3>
                    <p className="mt-1 text-base font-bold text-gray-900 dark:text-gray-100">
                        {formattedPrice}원
                    </p>
                </Link>

                {/* 찜하기(Heart) 버튼 */}
                <button
                    onClick={(e) => {
                        e.preventDefault();
                        setIsLiked(!isLiked);
                    }}
                    className="shrink-0 p-2 -mr-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    aria-label="찜하기"
                >
                    <Heart 
                        size={20} 
                        className={`transition-colors ${isLiked ? 'fill-red-500 text-red-500' : 'text-gray-400'}`} 
                    />
                </button>
            </div>
        </div>
    );
}