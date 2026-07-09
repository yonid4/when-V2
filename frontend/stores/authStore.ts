import { create } from 'zustand'
import { User } from '@/types'
import { logout } from '@/lib/api'
import { resetRealtimeTokenCache, supabase } from '@/lib/supabase'

// The session JWT lives ONLY in the HttpOnly `session` cookie set by the
// backend — this store never sees, stores, or writes a token (no localStorage,
// no JS-readable cookie). It holds the user object for UI state, nothing more.
interface AuthState {
  user: User | null
  setUser: (user: User) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => {
    // New session: drop any realtime token minted for a previous user, then
    // trigger the realtime client to pull a fresh one via its accessToken
    // callback (defined in lib/supabase.ts). Calling setAuth() with no args
    // uses the callback path — passing a token explicitly would override and
    // disable the callback.
    resetRealtimeTokenCache()
    supabase.realtime.setAuth()
    set({ user })
  },
  clearAuth: () => {
    // Ask the server to clear the HttpOnly session cookie (JS cannot).
    // Fire-and-forget: local state resets regardless of the network.
    void logout()
    resetRealtimeTokenCache()
    // Same — let the callback observe the now-missing session.
    supabase.realtime.setAuth()
    set({ user: null })
  },
}))
