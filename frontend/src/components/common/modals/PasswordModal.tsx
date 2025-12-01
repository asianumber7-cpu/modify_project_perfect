import React, { useState } from 'react';
import { X, Lock, CheckCircle2 } from 'lucide-react';
import client from '@/api/client';

interface PasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PasswordModal({ isOpen, onClose }: PasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      setMessage('새 비밀번호가 일치하지 않습니다.');
      return;
    }
    
    setLoading(true);
    setMessage(null);

    try {
      // 🚨 실제 백엔드 연동 시 엔드포인트: /api/v1/users/password-change (예시)
      // const response = await client.put('/api/v1/auth/password', { current_password: currentPassword, new_password: newPassword });
      
      // UI 테스트용 지연 처리 (1초)
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setMessage('비밀번호가 성공적으로 변경되었습니다!');
      
      // 성공 후 1.5초 뒤 닫기
      setTimeout(() => {
        onClose();
        setMessage(null);
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }, 1500);
      
    } catch (error) {
      console.error(error);
      setMessage('비밀번호 변경에 실패했습니다. 현재 비밀번호를 확인해주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in">
      {/* 모달 컨텐츠 */}
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-2xl overflow-hidden transform transition-all scale-100 mx-4">
        
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Lock size={18} className="text-purple-600" />
            비밀번호 변경
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* 폼 */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1">현재 비밀번호</label>
            <input 
              type="password" 
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-gray-50 dark:bg-gray-700 border-none focus:ring-2 focus:ring-purple-500 outline-none text-sm text-gray-900 dark:text-white transition-all"
              placeholder="현재 사용 중인 비밀번호"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1">새 비밀번호</label>
            <input 
              type="password" 
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-gray-50 dark:bg-gray-700 border-none focus:ring-2 focus:ring-purple-500 outline-none text-sm text-gray-900 dark:text-white transition-all"
              placeholder="영문, 숫자 포함 6자 이상"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1">새 비밀번호 확인</label>
            <input 
              type="password" 
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-gray-50 dark:bg-gray-700 border-none focus:ring-2 focus:ring-purple-500 outline-none text-sm text-gray-900 dark:text-white transition-all"
              placeholder="새 비밀번호를 한 번 더 입력"
              required
            />
          </div>

          {/* 피드백 메시지 */}
          {message && (
            <div className={`text-xs font-medium text-center py-2 rounded-lg flex items-center justify-center gap-1 ${message.includes('성공') ? 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'}`}>
              {message.includes('성공') && <CheckCircle2 size={14} />}
              {message}
            </div>
          )}

          {/* 버튼 그룹 */}
          <div className="flex gap-3 mt-6 pt-2">
            <button 
              type="button" 
              onClick={onClose}
              className="flex-1 py-3 rounded-xl bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-bold text-sm hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              취소
            </button>
            <button 
              type="submit" 
              disabled={loading}
              className="flex-1 py-3 rounded-xl bg-purple-600 text-white font-bold text-sm hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center justify-center"
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : '변경 완료'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}