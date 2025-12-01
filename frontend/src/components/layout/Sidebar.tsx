import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  X, ChevronRight, Star, Trash2, Settings, User, 
  Sun, Moon, LogOut 
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useSearchStore } from '@/store/searchStore';
import { useUIStore } from '@/store/uiStore';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { isDarkMode, toggleDarkMode } = useUIStore();
  
  const { recentSearches, favorites, removeRecentSearch, clearRecentSearches, toggleFavorite } = useSearchStore();

  const handleItemClick = (keyword: string) => {
    navigate(`/search?q=${encodeURIComponent(keyword)}`);
    onClose();
  };

  return (
    <>
      {/* 배경 오버레이 */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 dark:bg-black/60 z-40 transition-opacity backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      {/* 사이드바 본문 */}
      <div className={`fixed top-0 left-0 h-full w-80 bg-white dark:bg-[#1a1a1a] text-gray-900 dark:text-gray-300 z-50 transform transition-transform duration-300 ease-in-out shadow-2xl flex flex-col ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        
        {/* 1. 상단: 헤더 및 프로필 */}
        <div className="p-6 border-b border-gray-100 dark:border-gray-800">
          <div className="flex justify-between items-center mb-6">
             <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-blue-500">
               MODIFY
             </h2>
             <button onClick={onClose} className="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors">
              <X size={24} />
            </button>
          </div>

          {user ? (
            // 🚨 [수정됨] 여기 div에 onClick과 스타일을 추가했습니다.
            <div 
              onClick={() => {
                navigate('/profile'); // 프로필 페이지로 이동
                onClose(); // 사이드바 닫기
              }}
              className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-xl cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 group"
            >
              <div className="w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center text-purple-600 dark:text-purple-300 font-bold text-lg group-hover:scale-105 transition-transform">
                {user.email[0].toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <p className="text-sm font-bold text-gray-900 dark:text-white truncate">{user.email.split('@')[0]}</p>
                <p className="text-xs text-gray-500">Member</p>
              </div>
              {/* 화살표 아이콘 추가 (선택사항 - 이동 가능하다는 힌트) */}
              <ChevronRight size={16} className="ml-auto text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300" />
            </div>
          ) : (
            <Link 
              to="/login" 
              onClick={onClose}
              className="flex items-center justify-between w-full p-3 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 rounded-xl font-bold hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors"
            >
              <div className="flex items-center gap-2">
                <User size={20} />
                <span>로그인하기</span>
              </div>
              <ChevronRight size={18} />
            </Link>
          )}
        </div>

        {/* 2. 메인 컨텐츠 (즐겨찾기 & 최근 검색) */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 scrollbar-hide">
          
          {/* ⭐ 즐겨찾기 섹션 */}
          <div>
            <h3 className="flex items-center gap-2 text-sm font-bold text-orange-500 mb-3">
              <Star size={14} fill="currentColor" /> 즐겨찾기
            </h3>
            {favorites.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-600 py-2">즐겨찾는 스타일이 없습니다.</p>
            ) : (
              <ul className="space-y-2">
                {favorites.map((item, idx) => (
                  <li key={idx} className="group flex justify-between items-center p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer" onClick={() => handleItemClick(item)}>
                    <span className="text-sm text-gray-700 dark:text-gray-300 font-medium truncate w-full">
                      {item}
                    </span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); toggleFavorite(item); }}
                      className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity p-1"
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 🕒 최근 검색 섹션 */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-sm font-bold text-gray-900 dark:text-gray-400">최근 검색</h3>
              {recentSearches.length > 0 && (
                <button 
                  onClick={clearRecentSearches}
                  className="text-xs text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors"
                >
                  <Trash2 size={12} /> 전체 삭제
                </button>
              )}
            </div>
            
            {recentSearches.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-600 py-2">최근 검색 기록이 없습니다.</p>
            ) : (
              <ul className="space-y-2">
                {recentSearches.map((item, idx) => (
                  <li key={idx} className="group flex justify-between items-center p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer" onClick={() => handleItemClick(item)}>
                    <span className="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200 transition-colors truncate w-full">
                      {item}
                    </span>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={(e) => { e.stopPropagation(); toggleFavorite(item); }}
                        className={`p-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 ${favorites.includes(item) ? 'text-orange-500' : 'text-gray-400'}`}
                      >
                        <Star size={14} fill={favorites.includes(item) ? "currentColor" : "none"} />
                      </button>
                      <button 
                        onClick={(e) => { e.stopPropagation(); removeRecentSearch(item); }}
                        className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-gray-200 dark:hover:bg-gray-700"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* 3. 하단: 설정 및 테마 토글 */}
        <div className="p-6 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-[#1a1a1a] space-y-3">
          
          <button 
            onClick={toggleDarkMode}
            className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shadow-sm"
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              {isDarkMode ? <Moon size={16} className="text-purple-400" /> : <Sun size={16} className="text-orange-500" />}
              {isDarkMode ? '다크 모드' : '라이트 모드'}
            </span>
            <div className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-300 ${isDarkMode ? 'bg-purple-600' : 'bg-gray-300'}`}>
              <div className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform duration-300 ${isDarkMode ? 'translate-x-4' : 'translate-x-0'}`} />
            </div>
          </button>

          <div className="flex items-center justify-between px-2">
              {/* 🚨 [FIX] 설정 버튼에 클릭 이벤트 추가 */}
              <button 
                onClick={() => {
                  navigate('/settings'); // 설정 페이지로 이동
                  onClose(); // 사이드바 닫기
                }}
                className="flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-gray-900 dark:hover:text-gray-300 transition-colors"
              >
                <Settings size={14} />
              설정
            </button>
            
            {user && (
              <button 
                onClick={() => { logout(); onClose(); }}
                className="flex items-center gap-2 text-xs font-medium text-red-500 hover:text-red-600 transition-colors"
              >
                <LogOut size={14} />
                로그아웃
              </button>
            )}
          </div>
        </div>

      </div>
    </>
  );
}