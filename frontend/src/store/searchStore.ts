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
          const filtered = state.recentSearches.filter((item) => item !== keyword);
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
      name: 'search-history-storage',
    }
  )
);