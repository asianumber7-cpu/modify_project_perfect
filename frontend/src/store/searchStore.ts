import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SearchState {
  recentSearches: string[];
  favorites: string[];
  
  // 액션
  addRecentSearch: (keyword: string) => void;
  removeRecentSearch: (keyword: string) => void;
  clearRecentSearches: () => void;
  toggleFavorite: (keyword: string) => void;
}

export const useSearchStore = create<SearchState>()(
  persist(
    (set) => ({
      recentSearches: [],
      favorites: [],

      addRecentSearch: (keyword) =>
        set((state) => {
          // 중복 제거 및 최신 검색어가 위로 오도록 정렬
          const filtered = state.recentSearches.filter((item) => item !== keyword);
          // 최대 10개까지만 저장
          return { recentSearches: [keyword, ...filtered].slice(0, 10) };
        }),

      removeRecentSearch: (keyword) =>
        set((state) => ({
          recentSearches: state.recentSearches.filter((item) => item !== keyword),
        })),

      clearRecentSearches: () => set({ recentSearches: [] }),

      toggleFavorite: (keyword) =>
        set((state) => {
          const isExist = state.favorites.includes(keyword);
          return {
            favorites: isExist
              ? state.favorites.filter((item) => item !== keyword)
              : [keyword, ...state.favorites],
          };
        }),
    }),
    {
      name: 'search-history-storage', // 로컬 스토리지 키 이름
    }
  )
);