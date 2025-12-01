// src/hooks/useProducts.ts

import { useQuery } from '@tanstack/react-query';
import client from '@/api/client'; // client.ts 경로에 따라 수정
import { ProductResponse } from '@/types/index'; // ProductResponse 타입 임포트 가정

// 상품 조회 API 응답 타입 정의 (Schemas 기반)
// 실제 types/index.ts 파일에 정의되어 있어야 합니다.
// interface ProductResponse {
//   id: number;
//   name: string;
//   price: number;
//   // ... 기타 필드
// }

/**
 * 상품 목록을 조회하는 훅
 * @param params.skip 건너뛸 항목 수 (페이지네이션)
 * @param params.limit 조회할 항목 최대 수
 */
export const useProductList = (skip: number = 0, limit: number = 20) => {
  return useQuery<ProductResponse[]>({
    queryKey: ['products', skip, limit], // 쿼리 키에 페이지네이션 변수 포함
    queryFn: async () => {
      // 🚨 FastAPI 라우터 경로에 맞게 '/api/v1/products'가 아닌 '/v1/products'를 client가 사용하도록 설정되어 있다고 가정
      const { data } = await client.get(`/v1/products/`, {
        params: { skip, limit }
      });
      return data;
    },
    // 네트워크 연결이 느릴 경우를 대비한 옵션
    staleTime: 60 * 1000, // 1분 동안 데이터는 '신선'하다고 판단
  });
};

/**
 * 특정 상품 상세 정보를 조회하는 훅
 * @param productId 조회할 상품 ID
 */
export const useProductDetail = (productId: number | string | undefined) => {
  return useQuery<ProductResponse>({
    queryKey: ['product', productId],
    queryFn: async () => {
      if (!productId) throw new Error("Product ID is undefined.");
      const { data } = await client.get(`/v1/products/${productId}`);
      return data;
    },
    // ID가 유효할 때만 쿼리를 실행합니다.
    enabled: !!productId && productId !== 'undefined', 
  });
};