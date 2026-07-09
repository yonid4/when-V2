import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act } from 'react'

// ── Mock lib/api (clearAuth fires the logout endpoint) ────────────────────────
const mockLogout = vi.fn().mockResolvedValue(undefined)
vi.mock('@/lib/api', () => ({
  logout: () => mockLogout(),
  api: {},
}))

// ── Mock lib/supabase (realtime re-auth + token cache reset) ──────────────────
const mockSetAuth = vi.fn()
const mockResetRealtimeTokenCache = vi.fn()
vi.mock('@/lib/supabase', () => ({
  supabase: { realtime: { setAuth: () => mockSetAuth() } },
  resetRealtimeTokenCache: () => mockResetRealtimeTokenCache(),
}))

import { useAuthStore } from '@/stores/authStore'
import type { User } from '@/types'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  // Reset Zustand store between tests
  act(() => {
    useAuthStore.setState({ user: null })
  })
})

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    full_name: 'Alice',
    avatar_url: null,
    email_address: 'alice@example.com',
    timezone: null,
    primary_calendar_provider: 'google',
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    ...overrides,
  }
}

describe('authStore', () => {
  it('initial state has no user', () => {
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('setUser() sets the user and refreshes the realtime token path', () => {
    const user = makeUser()
    act(() => {
      useAuthStore.getState().setUser(user)
    })
    expect(useAuthStore.getState().user).toEqual(user)
    // Old realtime token dropped, then the client pulls a fresh one
    expect(mockResetRealtimeTokenCache).toHaveBeenCalledOnce()
    expect(mockSetAuth).toHaveBeenCalledOnce()
  })

  it('clearAuth() resets state, calls the logout endpoint, and re-auths realtime', () => {
    act(() => {
      useAuthStore.getState().setUser(makeUser())
    })
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().clearAuth()
    })
    expect(useAuthStore.getState().user).toBeNull()
    // The HttpOnly session cookie can only be cleared server-side
    expect(mockLogout).toHaveBeenCalledOnce()
    expect(mockResetRealtimeTokenCache).toHaveBeenCalledOnce()
    expect(mockSetAuth).toHaveBeenCalledOnce()
  })

  it('never persists a token: no localStorage writes, no JS-readable cookie', () => {
    act(() => {
      useAuthStore.getState().setUser(makeUser())
    })
    expect(localStorage.getItem('token')).toBeNull()
    expect(document.cookie).not.toContain('token=')
    act(() => {
      useAuthStore.getState().clearAuth()
    })
    expect(localStorage.getItem('token')).toBeNull()
    expect(document.cookie).not.toContain('token=')
  })
})
