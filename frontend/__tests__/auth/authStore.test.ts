import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act } from 'react'
import { useAuthStore } from '@/stores/authStore'
import type { User } from '@/types'

// authStore uses document.cookie — mock it for jsdom
const cookieStore: Record<string, string> = {}

beforeEach(() => {
  // Reset Zustand store between tests
  act(() => {
    useAuthStore.setState({ user: null, token: null })
  })
  // Clear localStorage
  localStorage.clear()
  // Reset cookie mock state
  Object.keys(cookieStore).forEach((k) => delete cookieStore[k])
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
  it('initial state has no user and no token', () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
  })

  it('setUser() sets the user and token in store', () => {
    const user = makeUser()
    act(() => {
      useAuthStore.getState().setUser(user, 'jwt-token-abc')
    })
    const state = useAuthStore.getState()
    expect(state.user).toEqual(user)
    expect(state.token).toBe('jwt-token-abc')
  })

  it('clearAuth() resets state to initial', () => {
    const user = makeUser()
    act(() => {
      useAuthStore.getState().setUser(user, 'jwt-token-abc')
    })
    act(() => {
      useAuthStore.getState().clearAuth()
    })
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
  })

  it('token persists in localStorage after setUser()', () => {
    const user = makeUser()
    act(() => {
      useAuthStore.getState().setUser(user, 'persisted-token')
    })
    expect(localStorage.getItem('token')).toBe('persisted-token')
  })

  it('token is cleared from localStorage after clearAuth()', () => {
    const user = makeUser()
    act(() => {
      useAuthStore.getState().setUser(user, 'persisted-token')
    })
    act(() => {
      useAuthStore.getState().clearAuth()
    })
    expect(localStorage.getItem('token')).toBeNull()
  })
})
