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

export interface RAGResult {
    answer: string;
    products?: ProductResponse[]; 
}

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

export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  image_url: string;
  category: string;
  gender?: string;
  is_active: boolean;
}

// [수정] 백엔드 응답 구조 반영
export interface CandidateImage {
    image_base64: string;
    score: number;
}

export interface AISearchResponse {
  status: string;
  strategy: string; 
  ai_analysis?: {
    summary: string;
    reference_image?: string; 
    candidates?: CandidateImage[]; // [NEW] 단순 문자열 배열 -> 객체 배열로 변경
  };
  products: Product[];
}