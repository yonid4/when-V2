import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from 'react'

// ── Mock next/navigation ─────────────────────────────────────────────────────
const mockReplace = vi.fn()
let mockToken: string | null = null

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({
    get: (key: string) => (key === 'token' ? mockToken : null),
  }),
}))

// ── Mock lib/api ──────────────────────────────────────────────────────────────
const mockApiGet = vi.fn()
vi.mock('@/lib/api', () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}))

// ── Mock authStore ─────────────────────────────────────────────────────────────
const mockSetUser = vi.fn()
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { setUser: typeof mockSetUser }) => unknown) =>
    selector({ setUser: mockSetUser }),
}))

import AuthCallbackPage from '@/app/auth/callback/page'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  mockToken = null
})

describe('AuthCallbackPage', () => {
  it('stores token in localStorage, calls setUser, and redirects to /dashboard when token is present', async () => {
    mockToken = 'valid-jwt-token'
    const fakeUser = {
      id: 'user-1',
      email_address: 'alice@example.com',
      full_name: 'Alice',
      avatar_url: null,
      timezone: null,
      primary_calendar_provider: 'google',
      created_at: '2026-04-01T00:00:00Z',
      updated_at: '2026-04-01T00:00:00Z',
    }
    mockApiGet.mockResolvedValueOnce(fakeUser)

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('valid-jwt-token')
      expect(mockSetUser).toHaveBeenCalledWith(fakeUser, 'valid-jwt-token')
      expect(mockReplace).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('redirects to / when no token param is present', async () => {
    mockToken = null

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/')
    })
    expect(localStorage.getItem('token')).toBeNull()
    expect(mockSetUser).not.toHaveBeenCalled()
  })

  it('redirects to / when API call fails', async () => {
    mockToken = 'some-token'
    mockApiGet.mockRejectedValueOnce(new Error('Unauthorized'))

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/')
    })
  })
})
