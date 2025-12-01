import { create } from 'zustand';

// RAG 상태 타입 정의
type RAGStatus = 'IDLE' | 'QUEUED' | 'PROCESSING' | 'SUCCESS' | 'FAILURE';

interface RAGState {
  taskId: string | null;
  status: RAGStatus;
  result: any | null; // 구체적인 타입은 types/index.ts에 정의된 것을 써도 됨
  
  // 액션
  setTaskId: (id: string) => void;
  updateStatus: (status: RAGStatus, result?: any) => void;
  reset: () => void;
}

export const useRAGStore = create<RAGState>((set) => ({
  taskId: null,
  status: 'IDLE',
  result: null,

  setTaskId: (id) => set({ taskId: id, status: 'QUEUED', result: null }),
  
  updateStatus: (status, result) => set((state) => ({
    status,
    result: result !== undefined ? result : state.result
  })),

  reset: () => set({ taskId: null, status: 'IDLE', result: null }),
}));