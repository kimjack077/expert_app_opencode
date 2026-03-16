import { create } from 'zustand'

interface AppState {
  collapsed: boolean
  theme: 'light' | 'dark'
  toggleCollapsed: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useAppStore = create<AppState>((set) => ({
  collapsed: false,
  theme: 'light',
  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
  setTheme: (theme) => set({ theme }),
}))
