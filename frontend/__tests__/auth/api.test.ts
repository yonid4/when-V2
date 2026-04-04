import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mock window.location ──────────────────────────────────────────────────────
const mockLocationAssign = vi.fn()
let locationHref = 'http://localhost:3000/dashboard'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()

  // Mock window.location.href setter
  Object.defineProperty(window, 'location', {
    value: {
      href: locationHref,
    },
    writable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ── Import api AFTER setting up the environment ────────────────────────────────
// We need to re-import for each test since module state (token) is read at call time

describe('lib/api', () => {
  it('attaches Authorization header when a token exists in localStorage', async () => {
    localStorage.setItem('token', 'my-jwt-token')

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
    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Authorization']).toBe('Bearer my-jwt-token')
  })

  it('sends no Authorization header when no token is in localStorage', async () => {
    // No token set

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
    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['Authorization']).toBeUndefined()
  })

  it('clears token from localStorage and redirects to / on 401 response', async () => {
    localStorage.setItem('token', 'expired-token')

    const mockFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    vi.stubGlobal('fetch', mockFetch)

    const { api } = await import('@/lib/api')

    await expect(api.get('/events')).rejects.toThrow('Unauthorized')

    expect(localStorage.getItem('token')).toBeNull()
    expect(window.location.href).toBe('/')
  })
})
