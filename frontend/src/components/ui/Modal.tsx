import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    maxWidth?: string;
}

export default function Modal({ 
    isOpen, 
    onClose, 
    title, 
    children,
    maxWidth = 'max-w-2xl'
}: ModalProps) {
    const modalRef = useRef<HTMLDivElement>(null);
    
    // ESC 키로 닫기
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        
        if (isOpen) {
            document.addEventListener('keydown', handleEsc);
            // 배경 스크롤 방지
            document.body.style.overflow = 'hidden';
        }
        
        return () => {
            document.removeEventListener('keydown', handleEsc);
            document.body.style.overflow = '';
        };
    }, [isOpen, onClose]);

    // 모달 외부 클릭 시 닫기
    const handleBackdropClick = (e: React.MouseEvent) => {
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    if (!isOpen) return null;

    return (
        <>
            {/* ✅ 수정: fixed + inset-0 으로 전체 화면 오버레이 */}
            <div 
                className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
                onClick={handleBackdropClick}
            >
                {/* 배경 오버레이 */}
                <div 
                    className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
                    aria-hidden="true"
                />
                
                {/* ✅ 수정: 모달 컨테이너 - 중앙 정렬 */}
                <div 
                    ref={modalRef}
                    className={`relative w-full ${maxWidth} bg-white rounded-2xl shadow-2xl 
                        transform animate-modal-enter
                        max-h-[85vh] flex flex-col overflow-hidden`}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby={title ? "modal-title" : undefined}
                >
                    {/* 헤더 - 고정 */}
                    {title && (
                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
                            <h2 id="modal-title" className="text-xl font-bold text-gray-900 flex items-center gap-2">
                                {title}
                            </h2>
                            <button 
                                onClick={onClose}
                                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-all"
                                aria-label="닫기"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                    )}
                    
                    {/* 닫기 버튼 (타이틀 없을 때) */}
                    {!title && (
                        <button 
                            onClick={onClose}
                            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-all z-10"
                            aria-label="닫기"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    )}
                    
                    {/* ✅ 수정: 내용 영역 - 스크롤 가능 */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {children}
                    </div>
                </div>
            </div>
            
            {/* 애니메이션 스타일 */}
            <style>{`
                @keyframes fade-in {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes modal-enter {
                    from { 
                        opacity: 0; 
                        transform: scale(0.95) translateY(10px); 
                    }
                    to { 
                        opacity: 1; 
                        transform: scale(1) translateY(0); 
                    }
                }
                .animate-fade-in {
                    animation: fade-in 0.2s ease-out forwards;
                }
                .animate-modal-enter {
                    animation: modal-enter 0.3s ease-out forwards;
                }
            `}</style>
        </>
    );
}