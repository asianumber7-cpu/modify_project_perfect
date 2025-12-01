import { create } from 'zustand';

interface UIState {
  isDarkMode: boolean;
  isBlindMode: boolean;
  toggleDarkMode: () => void;
  toggleBlindMode: () => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  isDarkMode: localStorage.getItem('theme') === 'dark',
  isBlindMode: false,

  toggleDarkMode: () => {
    const nextMode = !get().isDarkMode;
    set({ isDarkMode: nextMode });
    if (nextMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  },

  toggleBlindMode: () => set((state) => ({ isBlindMode: !state.isBlindMode })),
}));