import { render, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mock next/navigation ─────────────────────────────────────────────────────
const mockReplace = vi.fn()
let mockCode: string | null = null

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({
    get: (key: string) => (key === 'code' ? mockCode : null),
  }),
}))

// ── Mock lib/api ──────────────────────────────────────────────────────────────
const mockApiPost = vi.fn()
vi.mock('@/lib/api', () => ({
  api: { post: (...args: unknown[]) => mockApiPost(...args) },
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
  mockCode = null
})

describe('AuthCallbackPage', () => {
  it('exchanges the login code for a session, calls setUser with the user only, and redirects to /dashboard', async () => {
    mockCode = 'signed-login-code'
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
    mockApiPost.mockResolvedValueOnce(fakeUser)

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/auth/session/exchange', {
        code: 'signed-login-code',
      })
      expect(mockSetUser).toHaveBeenCalledWith(fakeUser)
      expect(mockReplace).toHaveBeenCalledWith('/dashboard')
    })
    // The JWT lives in the HttpOnly cookie — nothing token-like touches JS storage
    expect(localStorage.getItem('token')).toBeNull()
    expect(document.cookie).not.toContain('token=')
  })

  it('redirects to / when no code param is present', async () => {
    mockCode = null

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/')
    })
    expect(mockApiPost).not.toHaveBeenCalled()
    expect(mockSetUser).not.toHaveBeenCalled()
  })

  it('redirects to / when the exchange fails (expired/tampered code)', async () => {
    mockCode = 'stale-code'
    mockApiPost.mockRejectedValueOnce(new Error('Unauthorized'))

    render(<AuthCallbackPage />)

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/')
    })
    expect(mockSetUser).not.toHaveBeenCalled()
  })
})
