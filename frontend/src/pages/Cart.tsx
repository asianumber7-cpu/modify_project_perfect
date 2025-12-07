import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
    ShoppingBag, Trash2, Plus, Minus, ArrowLeft, 
    ShoppingCart, CreditCard, AlertCircle 
} from 'lucide-react';

interface CartItem {
    id: number;
    name: string;
    price: number;
    image_url: string;
    quantity: number;
}

export default function Cart() {
    const navigate = useNavigate();
    const [cartItems, setCartItems] = useState<CartItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // 장바구니 불러오기
    useEffect(() => {
        const loadCart = () => {
            try {
                const saved = localStorage.getItem('cart');
                if (saved) {
                    setCartItems(JSON.parse(saved));
                }
            } catch (error) {
                console.error('Failed to load cart:', error);
            } finally {
                setIsLoading(false);
            }
        };
        loadCart();
    }, []);

    // 장바구니 저장
    const saveCart = (items: CartItem[]) => {
        localStorage.setItem('cart', JSON.stringify(items));
        setCartItems(items);
    };

    // 수량 변경
    const updateQuantity = (id: number, delta: number) => {
        const updated = cartItems.map(item => {
            if (item.id === id) {
                const newQty = Math.max(1, item.quantity + delta);
                return { ...item, quantity: newQty };
            }
            return item;
        });
        saveCart(updated);
    };

    // 아이템 삭제
    const removeItem = (id: number) => {
        const updated = cartItems.filter(item => item.id !== id);
        saveCart(updated);
    };

    // 전체 삭제
    const clearCart = () => {
        if (window.confirm('장바구니를 비우시겠습니까?')) {
            saveCart([]);
        }
    };

    // 결제하기
    const handleCheckout = () => {
        if (cartItems.length === 0) {
            alert('장바구니가 비어있습니다.');
            return;
        }
        navigate('/checkout');
    };

    // 총 금액 계산
    const totalPrice = cartItems.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const totalItems = cartItems.reduce((sum, item) => sum + item.quantity, 0);

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {/* 헤더 */}
            <div className="mb-8">
                <button 
                    onClick={() => navigate(-1)}
                    className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm font-medium mb-4"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> 쇼핑 계속하기
                </button>
                <div className="flex items-center justify-between">
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        <ShoppingCart className="w-8 h-8 text-purple-600" />
                        장바구니
                        {totalItems > 0 && (
                            <span className="text-lg font-normal text-gray-500">({totalItems}개)</span>
                        )}
                    </h1>
                    {cartItems.length > 0 && (
                        <button 
                            onClick={clearCart}
                            className="text-sm text-red-500 hover:text-red-700 font-medium"
                        >
                            전체 삭제
                        </button>
                    )}
                </div>
            </div>

            {cartItems.length === 0 ? (
                /* 빈 장바구니 */
                <div className="text-center py-20">
                    <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                        <ShoppingBag className="w-12 h-12 text-gray-400" />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 mb-2">장바구니가 비어있습니다</h2>
                    <p className="text-gray-500 mb-8">마음에 드는 상품을 담아보세요!</p>
                    <Link 
                        to="/search"
                        className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 text-white font-bold rounded-xl hover:bg-purple-700 transition-colors"
                    >
                        <ShoppingBag className="w-5 h-5" /> 쇼핑하러 가기
                    </Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* 상품 목록 */}
                    <div className="lg:col-span-2 space-y-4">
                        {cartItems.map((item) => (
                            <div 
                                key={item.id}
                                className="bg-white rounded-2xl border border-gray-200 p-4 flex gap-4 hover:shadow-md transition-shadow"
                            >
                                {/* 이미지 */}
                                <Link to={`/products/${item.id}`} className="shrink-0">
                                    <div className="w-24 h-24 sm:w-32 sm:h-32 bg-gray-100 rounded-xl overflow-hidden">
                                        <img 
                                            src={item.image_url || '/placeholder.png'} 
                                            alt={item.name}
                                            className="w-full h-full object-cover hover:scale-105 transition-transform"
                                            onError={(e) => (e.currentTarget.src = '/placeholder.png')}
                                        />
                                    </div>
                                </Link>

                                {/* 정보 */}
                                <div className="flex-1 flex flex-col justify-between min-w-0">
                                    <div>
                                        <Link 
                                            to={`/products/${item.id}`}
                                            className="font-bold text-gray-900 hover:text-purple-600 transition-colors line-clamp-2"
                                        >
                                            {item.name}
                                        </Link>
                                        <p className="text-lg font-bold text-gray-900 mt-1">
                                            {item.price.toLocaleString()}원
                                        </p>
                                    </div>

                                    {/* 수량 조절 & 삭제 */}
                                    <div className="flex items-center justify-between mt-3">
                                        <div className="flex items-center gap-2">
                                            <button 
                                                onClick={() => updateQuantity(item.id, -1)}
                                                disabled={item.quantity <= 1}
                                                className="w-8 h-8 rounded-lg border border-gray-300 flex items-center justify-center hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                            >
                                                <Minus className="w-4 h-4" />
                                            </button>
                                            <span className="w-10 text-center font-bold">{item.quantity}</span>
                                            <button 
                                                onClick={() => updateQuantity(item.id, 1)}
                                                className="w-8 h-8 rounded-lg border border-gray-300 flex items-center justify-center hover:bg-gray-100 transition-colors"
                                            >
                                                <Plus className="w-4 h-4" />
                                            </button>
                                        </div>
                                        <button 
                                            onClick={() => removeItem(item.id)}
                                            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                        >
                                            <Trash2 className="w-5 h-5" />
                                        </button>
                                    </div>
                                </div>

                                {/* 소계 (데스크탑) */}
                                <div className="hidden sm:flex flex-col items-end justify-center">
                                    <span className="text-sm text-gray-500">소계</span>
                                    <span className="text-xl font-bold text-gray-900">
                                        {(item.price * item.quantity).toLocaleString()}원
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* 주문 요약 */}
                    <div className="lg:col-span-1">
                        <div className="bg-gray-50 rounded-2xl p-6 border border-gray-200 sticky top-24">
                            <h2 className="text-lg font-bold text-gray-900 mb-4">주문 요약</h2>
                            
                            <div className="space-y-3 mb-6">
                                <div className="flex justify-between text-gray-600">
                                    <span>상품 금액</span>
                                    <span>{totalPrice.toLocaleString()}원</span>
                                </div>
                                <div className="flex justify-between text-gray-600">
                                    <span>배송비</span>
                                    <span className={totalPrice >= 50000 ? 'text-green-600' : ''}>
                                        {totalPrice >= 50000 ? '무료' : '3,000원'}
                                    </span>
                                </div>
                                {totalPrice < 50000 && (
                                    <div className="flex items-start gap-2 text-xs text-blue-600 bg-blue-50 p-3 rounded-lg">
                                        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                                        <span>{(50000 - totalPrice).toLocaleString()}원 더 담으면 무료배송!</span>
                                    </div>
                                )}
                                <div className="border-t border-gray-200 pt-3">
                                    <div className="flex justify-between text-lg font-bold text-gray-900">
                                        <span>총 결제금액</span>
                                        <span className="text-purple-600">
                                            {(totalPrice + (totalPrice >= 50000 ? 0 : 3000)).toLocaleString()}원
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <button 
                                onClick={handleCheckout}
                                className="w-full py-4 bg-purple-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-purple-700 transition-colors shadow-lg active:scale-95"
                            >
                                <CreditCard className="w-5 h-5" /> 결제하기
                            </button>

                            <p className="text-xs text-gray-400 text-center mt-4">
                                주문 내용을 확인하였으며, 결제에 동의합니다.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}