// src/components/routes/AdminRoute.tsx

import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

/**
 * 관리자 권한이 필요한 라우트를 보호하는 컴포넌트.
 * 비로그인 사용자나 일반 사용자는 /login으로 리다이렉트됩니다.
 */
export default function AdminRoute() {
  // 전역 상태에서 사용자 정보 가져오기
  const { user } = useAuthStore();
  
  // 로딩 상태 처리 (만약 초기 로딩 시 user가 null일 경우)
  // 현재 AuthStore 구조에서는 동기적으로 로컬 스토리지에서 로드하므로 별도 로딩 처리는 생략합니다.
  
  // 1. 사용자 객체가 없거나 (비로그인)
  // 2. 사용자가 슈퍼 관리자(is_superuser)가 아닐 경우
  if (!user || !user.is_superuser) {
    // 권한이 없으므로 로그인 페이지로 강제 이동
    console.warn("Access Denied: Attempted to access admin route without superuser privilege.");
    return <Navigate to="/login" replace />; 
  }

  // 관리자 권한이 있는 경우: 자식 라우트 컴포넌트 렌더링
  return <Outlet />;
}