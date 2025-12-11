
// 백엔드 API URL (환경변수 또는 기본값)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// 플레이스홀더 이미지
const PLACEHOLDER_IMAGE = 'https://placehold.co/400x500/e2e8f0/64748b?text=No+Image';

/**
 * 이미지 URL을 전체 URL로 변환
 * @param imageUrl - 이미지 URL (/static/images/... 또는 http://...)
 * @returns 전체 URL (http://localhost:8000/static/images/...)
 */
export const getImageUrl = (imageUrl: string | null | undefined): string => {
  if (!imageUrl) {
    return PLACEHOLDER_IMAGE;
  }
  
  // 이미 전체 URL인 경우 그대로 반환
  if (imageUrl.startsWith('http://') || imageUrl.startsWith('https://')) {
    return imageUrl;
  }
  
  // data: URL인 경우 그대로 반환 (base64 이미지)
  if (imageUrl.startsWith('data:')) {
    return imageUrl;
  }
  
  // /static/images/... 형식이면 백엔드 URL 붙이기
  if (imageUrl.startsWith('/static/')) {
    return `${API_BASE_URL}${imageUrl}`;
  }
  
  // 그 외의 경우도 백엔드 URL 붙이기
  return `${API_BASE_URL}${imageUrl.startsWith('/') ? '' : '/'}${imageUrl}`;
};

/**
 * 캐시 버스팅이 적용된 이미지 URL 반환
 * @param imageUrl - 이미지 URL
 * @param timestamp - 타임스탬프 (선택)
 * @returns 캐시 버스팅이 적용된 URL
 */
export const getBustedImageUrl = (imageUrl: string | null | undefined, timestamp?: number): string => {
  const url = getImageUrl(imageUrl);
  
  if (url === PLACEHOLDER_IMAGE) {
    return url;
  }
  
  const ts = timestamp || Date.now();
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}t=${ts}`;
};

export { API_BASE_URL, PLACEHOLDER_IMAGE };