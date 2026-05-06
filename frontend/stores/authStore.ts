import { create } from 'zustand'
import { User } from '@/types'
import { addDays } from '@/lib/dates'
import { supabase } from '@/lib/supabase'

interface AuthState {
  user: User | null
  token: string | null
  setUser: (user: User, token: string) => void
  clearAuth: () => void
}

function setCookie(name: string, value: string, days: number) {
  const expires = addDays(new Date(), days).toUTCString()
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
    // Trigger the realtime client to re-read the token via its accessToken
    // callback (defined in lib/supabase.ts) and re-authenticate any open
    // channels. Calling setAuth() with no args uses the callback path —
    // passing a token explicitly would override and disable the callback.
    supabase.realtime.setAuth()
    set({ user, token })
  },
  clearAuth: () => {
    localStorage.removeItem('token')
    deleteCookie('token')
    // Same — let the callback observe the now-empty localStorage.
    supabase.realtime.setAuth()
    set({ user: null, token: null })
  },
}))
