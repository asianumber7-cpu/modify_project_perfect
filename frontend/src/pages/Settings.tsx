import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Settings as SettingsIcon, 
  Bell, Shield, Smartphone, ChevronRight, 
  ArrowLeft, Loader2 
} from 'lucide-react';
import { useUIStore } from '@/store/uiStore';
import client from '@/api/client';
import PasswordModal from '@/components/common/modals/PasswordModal';
import TwoFactorModal from '@/components/common/modals/TwoFactorModal';
import { User } from '@/types'; 

export default function Settings() {
  const navigate = useNavigate();
  const { isDarkMode, toggleDarkMode } = useUIStore();
  
  // UI 상태
  const [notifications, setNotifications] = useState(true); 
  
  // 사용자 데이터 상태
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // 모달 상태
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [is2FAModalOpen, setIs2FAModalOpen] = useState(false);

  // 1. 내 정보 불러오기 (마케팅 수신 동의 상태 확인)
  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await client.get<User>('/api/v1/users/me');
        setUser(res.data);
      } catch (error) {
        console.error('Failed to fetch user settings', error);
      } finally {
        setLoading(false);
      }
    };
    fetchMe();
  }, []);

  // 2. 마케팅 수신 동의 토글 핸들러
  const toggleMarketing = async () => {
    if (!user) return;

    const previousState = user.is_marketing_agreed;
    const newState = !previousState;

    // 낙관적 업데이트 (UI 먼저 변경)
    setUser({ ...user, is_marketing_agreed: newState });

    try {
      await client.patch('/api/v1/users/me', {
        is_marketing_agreed: newState
      });
      console.log('Marketing consent updated:', newState);
    } catch (error) {
      console.error('Update failed', error);
      // 실패 시 롤백
      setUser({ ...user, is_marketing_agreed: previousState });
      alert('설정 변경에 실패했습니다.');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto px-6 py-10 animate-fade-in-up">
      
      {/* 헤더 영역 */}
      <div className="flex items-center gap-3 mb-8">
        <button 
          onClick={() => navigate(-1)}
          className="p-2 -ml-2 rounded-full text-gray-500 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white transition-all"
          aria-label="뒤로가기"
        >
          <ArrowLeft size={24} />
        </button>
        
        <div className="flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-gray-900 dark:text-white" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">설정</h1>
        </div>
      </div>

      <div className="space-y-6">
        
        {/* 1. 알림 설정 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700">
          <h2 className="text-sm font-bold text-gray-500 dark:text-gray-400 mb-4 flex items-center gap-2">
            <Bell size={16} /> 알림
          </h2>
          
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-bold text-gray-900 dark:text-white">푸시 알림</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">서비스 주요 알림을 받습니다.</p>
              </div>
              <button 
                onClick={() => setNotifications(!notifications)}
                className={`w-11 h-6 rounded-full transition-colors duration-200 ease-in-out relative ${notifications ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-600'}`}
              >
                <span className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transition-transform duration-200 ${notifications ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>

            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-bold text-gray-900 dark:text-white">마케팅 정보 수신</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">이벤트 및 혜택 정보를 받습니다.</p>
              </div>
              {/* 실제 API와 연동된 버튼 */}
              <button 
                onClick={toggleMarketing}
                className={`w-11 h-6 rounded-full transition-colors duration-200 ease-in-out relative ${user?.is_marketing_agreed ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-600'}`}
              >
                <span className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transition-transform duration-200 ${user?.is_marketing_agreed ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* 2. 보안 및 계정 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700">
          <h2 className="text-sm font-bold text-gray-500 dark:text-gray-400 mb-4 flex items-center gap-2">
            <Shield size={16} /> 보안
          </h2>
          
          <div className="space-y-4">
            <button 
              onClick={() => setIsPasswordModalOpen(true)}
              className="w-full flex justify-between items-center py-2 group cursor-pointer"
            >
              <span className="text-sm font-bold text-gray-900 dark:text-white">비밀번호 변경</span>
              <ChevronRight size={16} className="text-gray-400 group-hover:text-indigo-600 transition-colors" />
            </button>
            
            <button 
              onClick={() => setIs2FAModalOpen(true)}
              className="w-full flex justify-between items-center py-2 group cursor-pointer"
            >
              <span className="text-sm font-bold text-gray-900 dark:text-white">2단계 인증 설정</span>
              <ChevronRight size={16} className="text-gray-400 group-hover:text-indigo-600 transition-colors" />
            </button>
          </div>
        </div>

        {/* 3. 앱 설정 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-gray-700">
           <h2 className="text-sm font-bold text-gray-500 dark:text-gray-400 mb-4 flex items-center gap-2">
            <Smartphone size={16} /> 앱 설정
          </h2>

          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm font-bold text-gray-900 dark:text-white">다크 모드</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">어두운 테마를 적용합니다.</p>
            </div>
            <button 
              onClick={toggleDarkMode}
              className={`w-11 h-6 rounded-full transition-colors duration-200 ease-in-out relative ${isDarkMode ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-600'}`}
            >
              <span className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transition-transform duration-200 ${isDarkMode ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>
        </div>

      </div>

      <PasswordModal 
        isOpen={isPasswordModalOpen} 
        onClose={() => setIsPasswordModalOpen(false)} 
      />
      <TwoFactorModal 
        isOpen={is2FAModalOpen} 
        onClose={() => setIs2FAModalOpen(false)} 
      />

    </div>
  );
}