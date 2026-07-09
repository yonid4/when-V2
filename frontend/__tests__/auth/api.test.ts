import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mock authStore (api.ts calls clearAuth on 401) ────────────────────────────
const mockClearAuth = vi.fn()
vi.mock('@/stores/authStore', () => ({
  useAuthStore: {
    getState: () => ({ clearAuth: mockClearAuth }),
  },
}))

// ── Mock window.location ──────────────────────────────────────────────────────
let locationHref = 'http://localhost:3000/dashboard'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()

  // Mock window.location.href setter
  Object.defineProperty(window, 'location', {
    value: {
      href: locationHref,
      pathname: '/dashboard',
    },
    writable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('lib/api', () => {
  it('never attaches an Authorization header — auth rides on the HttpOnly session cookie', async () => {
    // Even a legacy token left in localStorage must be ignored
    localStorage.setItem('token', 'legacy-jwt-token')

    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 'data' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('@/lib/api')
    await api.get('/events')

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/events')
    expect(options.headers['Authorization']).toBeUndefined()
    // Same-origin fetch sends cookies by default — no credentials override needed
    expect(options.credentials).toBeUndefined()
  })

  it('clears auth state and redirects to / on 401 response', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('@/lib/api')

    await expect(api.get('/events')).rejects.toThrow('Unauthorized')

    expect(mockClearAuth).toHaveBeenCalledOnce()
    expect(window.location.href).toBe('/')
  })

  it('logout() posts to /api/auth/logout with keepalive and never throws', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', mockFetch)

    const { logout } = await import('@/lib/api')
    await expect(logout()).resolves.toBeUndefined()

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/auth/logout')
    expect(options.method).toBe('POST')
    // keepalive lets the request survive the navigation that follows clearAuth
    expect(options.keepalive).toBe(true)
  })

  it('logout() swallows network errors', async () => {
    const mockFetch = vi.fn().mockRejectedValueOnce(new Error('network down'))
    vi.stubGlobal('fetch', mockFetch)

    const { logout } = await import('@/lib/api')
    await expect(logout()).resolves.toBeUndefined()
  })
})
