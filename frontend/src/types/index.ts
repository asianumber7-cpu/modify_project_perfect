// src/types/index.ts

// --- Product & Forms ---
export interface ProductResponse {
    id: number;
    name: string;
    description: string | null;
    price: number;
    stock_quantity: number;
    category: string | null;
    image_url: string | null;
    in_stock: boolean;
    created_at: string; // ISO String
    updated_at: string; // ISO String
}

export interface ProductCreateForm {
    name: string;
    description: string;
    price: number;
    stock_quantity: number;
    category: string;
    image_url: string;
}

// --- RAG & AI ---
export type RAGStatus = 'QUEUED' | 'PROCESSING' | 'SUCCESS' | 'FAILURE';

// RAG 결과의 답변 및 추천 상품 목록
export interface RAGResult {
    answer: string;
    products?: ProductResponse[]; 
}

// RAG 작업 상태 응답
export interface RAGTaskResponse {
    task_id: string | null;
    status: RAGStatus;
    progress: number;
    result?: RAGResult;
}

// --- Auth ---
export interface User {
    id: number;
    email: string;
    full_name?: string; 
    is_superuser: boolean;
    is_marketing_agreed: boolean; 
}