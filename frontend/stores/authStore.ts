import { create } from 'zustand'
import { User } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  setUser: (user: User, token: string) => void
  clearAuth: () => void
}

function setCookie(name: string, value: string, days: number) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString()
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Lax`
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  setUser: (user, token) => {
    localStorage.setItem('token', token)
    setCookie('token', token, 7)
    set({ user, token })
  },
  clearAuth: () => {
    localStorage.removeItem('token')
    deleteCookie('token')
    set({ user: null, token: null })
  },
}))
