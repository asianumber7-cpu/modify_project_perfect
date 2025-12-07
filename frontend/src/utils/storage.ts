// src/utils/storage.ts (CryptoJS를 이용한 AES 암호화/복호화)

import CryptoJS from 'crypto-js';

// VITE 환경 변수를 로드합니다. (Docker 및 CI/CD 환경에서 이 변수가 반드시 설정되어야 합니다.)
const SECRET_KEY = import.meta.env.VITE_ENCRYPTION_KEY || 'development_secret_key_DO_NOT_USE';

/**
 * 보안 저장소 유틸리티 (JWT 및 민감 정보를 AES 암호화하여 localStorage에 저장)
 */
export const storage = {
  
  /**
   * 값을 암호화하여 로컬 스토리지에 저장합니다.
   * @param key 로컬 스토리지 키
   * @param value 저장할 값 (객체 또는 문자열)
   */
  setSecureItem: (key: string, value: any) => {
    try {
      const stringValue = JSON.stringify(value);
      // AES 암호화
      const encrypted = CryptoJS.AES.encrypt(stringValue, SECRET_KEY).toString();
      localStorage.setItem(key, encrypted);
    } catch (error) {
      console.error('Encryption failed', error);
      // 암호화 실패 시 저장하지 않음
    }
  },

  /**
   * 로컬 스토리지에서 값을 복호화하여 가져옵니다.
   * @param key 로컬 스토리지 키
   * @returns 복호화된 값 또는 null
   */
  getSecureItem: (key: string) => {
    try {
      const encrypted = localStorage.getItem(key);
      if (!encrypted) return null;

      // AES 복호화
      const bytes = CryptoJS.AES.decrypt(encrypted, SECRET_KEY);
      const decrypted = bytes.toString(CryptoJS.enc.Utf8);
      
      if (!decrypted) return null;
      // 복호화된 JSON 문자열을 객체로 변환
      return JSON.parse(decrypted);
    } catch (error) {
      console.error('Decryption failed', error);
      // 복호화 실패 시 (변조, 키 변경 등) 해당 키 삭제 후 null 반환
      localStorage.removeItem(key);
      return null;
    }
  },

  removeSecureItem: (key: string) => {
    localStorage.removeItem(key);
  }
};