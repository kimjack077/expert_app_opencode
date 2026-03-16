import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '@/services/api'

interface User {
  id: string
  username: string
  email?: string
  full_name?: string
  role: string
  is_active: boolean
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  setTokens: (token: string, refreshToken: string) => void
  fetchUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        const res: any = await authApi.login(username, password)
        const { access_token, refresh_token, user } = res.data
        set({
          token: access_token,
          refreshToken: refresh_token,
          user,
          isAuthenticated: true,
        })
      },

      logout: () => {
        set({
          token: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        })
      },

      setTokens: (token: string, refreshToken: string) => {
        set({ token, refreshToken })
      },

      fetchUser: async () => {
        const res: any = await authApi.getMe()
        set({ user: res.data })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
