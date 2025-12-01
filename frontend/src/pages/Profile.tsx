import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { MousePointer2, ChevronRight, CheckCircle2, ArrowLeft } from 'lucide-react';
import Modal from '@/components/ui/Modal';

// API URL
const API_BASE_URL = 'http://localhost:8000/api/v1';

export default function Profile() {
  const navigate = useNavigate();
  const { user, token, setUser } = useAuthStore();

  const [activeModal, setActiveModal] = useState<'name' | 'password' | 'phone' | 'reset' | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // 폼 상태
  const [newName, setNewName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [newPhone, setNewPhone] = useState('');

  const handleGoBack = () => navigate(-1);

  const closeModal = () => {
    setActiveModal(null);
    setNewName('');
    setNewPassword('');
    setConfirmPassword('');
    setNewPhone('');
  };

  // ----------------------------------------------------------------------
  // ✨ 마스킹 헬퍼 함수들
  // ----------------------------------------------------------------------
  
  // 이메일 마스킹 (abc***@naver.com)
  const maskEmail = (email: string) => {
    if (!email) return '';
    const [name, domain] = email.split('@');
    const maskedName = name.length > 3 ? name.slice(0, 3) + '*'.repeat(name.length - 3) : name;
    return `${maskedName}@${domain}`;
  };

  // ✨ 휴대폰 번호 마스킹 (010-****-5678)
  const formatPhoneNumber = (phone: string | undefined) => {
    // 1. 데이터가 없으면 기본값 표시
    if (!phone) return '010-****-**** (미등록)';

    // 2. 숫자만 추출
    const clean = phone.replace(/[^0-9]/g, '');

    // 3. 길이에 따른 마스킹 처리
    if (clean.length === 11) {
      // 010-1234-5678 -> 010-****-5678
      return `${clean.slice(0, 3)}-****-${clean.slice(7)}`;
    } else if (clean.length === 10) {
      // 010-123-4567 -> 010-***-4567
      return `${clean.slice(0, 3)}-***-${clean.slice(6)}`;
    }

    // 형식이 안 맞으면 그냥 원본 출력 (혹은 보안을 위해 전체 마스킹)
    return phone;
  };

  // ----------------------------------------------------------------------
  // API 통신
  // ----------------------------------------------------------------------
  const updateProfile = async (data: object, successMessage: string) => {
    if (!token) return;
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/users/me`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `서버 오류 (${response.status})`);
      }

      const updatedUser = await response.json();
      setUser(updatedUser); // 스토어 업데이트 (여기서 DB 데이터로 덮어씌워짐)
      alert(successMessage);
      closeModal();

    } catch (error: any) {
      console.error(error);
      alert(`업데이트 실패: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmitName = () => {
    if (!newName.trim()) return alert('이름을 입력해주세요.');
    updateProfile({ full_name: newName }, '이름이 변경되었습니다.');
  };

  const handleSubmitPassword = () => {
    if (newPassword.length < 6) return alert('비밀번호는 6자 이상이어야 합니다.');
    if (newPassword !== confirmPassword) return alert('비밀번호가 일치하지 않습니다.');
    updateProfile({ password: newPassword }, '비밀번호가 변경되었습니다.');
  };

  const handleSubmitPhone = () => {
    // 입력값에서 하이픈 제거하고 전송
    const cleanPhone = newPhone.replace(/-/g, '');
    if (cleanPhone.length < 10) return alert('올바른 휴대폰 번호를 입력해주세요.');
    
    updateProfile({ phone_number: cleanPhone }, '휴대폰 번호가 변경되었습니다.');
  };

  const handleSubmitReset = () => {
    alert('본인인증 정보가 초기화되었습니다.');
    closeModal();
  };

  if (!user) return <div className="p-10 text-center">로그인 정보를 불러오는 중입니다...</div>;

  return (
    <div className="w-full max-w-5xl mx-auto px-6 py-10 animate-fade-in-up">
      {/* 헤더 */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={handleGoBack} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
          <ArrowLeft className="w-6 h-6 text-gray-900" />
        </button>
        <div className="flex items-center gap-2">
          <MousePointer2 className="w-6 h-6 text-black fill-black" />
          <h1 className="text-2xl font-bold text-gray-900">계정정보</h1>
        </div>
      </div>

      {/* 메인 카드 */}
      <div className="bg-white rounded-[20px] shadow-sm border border-gray-100 p-8 sm:p-10">
        <section className="mb-12">
          <h2 className="text-sm font-bold text-gray-500 mb-6">프로필</h2>
          <div className="space-y-8">
            
            {/* ID */}
            <div className="flex justify-between items-center group">
              <div className="flex items-center w-1/3">
                <span className="text-sm font-medium text-gray-600 w-24">Modify ID</span>
                <span className="text-sm font-bold text-gray-900">{maskEmail(user.email)}</span>
              </div>
              <button className="flex items-center text-xs font-bold text-gray-300 cursor-not-allowed">
                변경 불가
              </button>
            </div>

            {/* 비밀번호 */}
            <div className="flex justify-between items-center group cursor-pointer" onClick={() => setActiveModal('password')}>
              <div className="flex items-center w-1/3">
                <span className="text-sm font-medium text-gray-600 w-24">비밀번호</span>
                <span className="text-sm font-bold text-gray-900 tracking-widest">********</span>
              </div>
              <button className="flex items-center text-xs font-bold text-gray-400 group-hover:text-gray-600 transition-colors">
                변경 <ChevronRight className="w-4 h-4 text-[#4ADE80] ml-1" />
              </button>
            </div>

            {/* 이름 */}
            <div className="flex justify-between items-center group cursor-pointer" onClick={() => { setNewName(user.full_name || ''); setActiveModal('name'); }}>
              <div className="flex items-center w-1/3">
                <span className="text-sm font-medium text-gray-600 w-24">이름</span>
                <span className="text-sm font-bold text-gray-900">{user.full_name || '이름 없음'}</span>
              </div>
              <button className="flex items-center text-xs font-bold text-gray-400 group-hover:text-gray-600 transition-colors">
                변경 <ChevronRight className="w-4 h-4 text-[#4ADE80] ml-1" />
              </button>
            </div>

            {/* 휴대폰 - ✨ 마스킹 적용됨 */}
            <div className="flex justify-between items-center group cursor-pointer" onClick={() => { setNewPhone(user.phone_number || ''); setActiveModal('phone'); }}>
              <div className="flex items-center w-1/3">
                <span className="text-sm font-medium text-gray-600 w-24">휴대폰</span>
                <span className="text-sm font-bold text-gray-900">
                  {formatPhoneNumber(user.phone_number)}
                </span>
              </div>
              <div className="flex gap-3">
                <button className="flex items-center text-xs font-bold text-gray-400 group-hover:text-gray-600 transition-colors">
                  변경 <span className="w-[1px] h-3 bg-gray-300 mx-2"></span> 삭제 
                  <ChevronRight className="w-4 h-4 text-[#4ADE80] ml-1" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <div className="w-full h-[1px] bg-gray-100 mb-10"></div>

        <section>
          <h2 className="text-sm font-bold text-gray-500 mb-6">본인확인</h2>
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-gray-900">본인확인 완료</span>
              <CheckCircle2 className={`w-4 h-4 ${user.is_active ? 'text-[#FF5A5A]' : 'text-gray-300'} fill-current`} />
            </div>
            <button onClick={() => setActiveModal('reset')} className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-all shadow-sm">
              본인인증 초기화
            </button>
          </div>
        </section>
      </div>

      {/* 모달들 */}
      <Modal isOpen={activeModal === 'name'} onClose={closeModal} title="이름 변경">
        <div className="space-y-4">
          <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="새 이름" />
          <button onClick={handleSubmitName} disabled={isLoading} className="w-full py-3 bg-black text-white rounded-lg font-bold">{isLoading ? '처리 중...' : '저장하기'}</button>
        </div>
      </Modal>

      <Modal isOpen={activeModal === 'password'} onClose={closeModal} title="비밀번호 변경">
        <div className="space-y-4">
          <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="새 비밀번호" />
          <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="비밀번호 확인" />
          <button onClick={handleSubmitPassword} disabled={isLoading} className="w-full py-3 bg-black text-white rounded-lg font-bold">{isLoading ? '처리 중...' : '변경하기'}</button>
        </div>
      </Modal>

      <Modal isOpen={activeModal === 'phone'} onClose={closeModal} title="휴대폰 번호 변경">
        <div className="space-y-4">
          <input type="text" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="01012345678 (하이픈 없이)" />
          <button onClick={handleSubmitPhone} disabled={isLoading} className="w-full py-3 bg-black text-white rounded-lg font-bold">{isLoading ? '처리 중...' : '저장하기'}</button>
        </div>
      </Modal>

      <Modal isOpen={activeModal === 'reset'} onClose={closeModal} title="본인인증 초기화">
        <div className="text-center space-y-6">
          <p className="text-gray-600">정말 초기화 하시겠습니까?</p>
          <div className="flex gap-3">
            <button onClick={closeModal} className="flex-1 py-3 bg-gray-100 rounded-lg font-bold">취소</button>
            <button onClick={handleSubmitReset} className="flex-1 py-3 bg-red-500 text-white rounded-lg font-bold">초기화</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
