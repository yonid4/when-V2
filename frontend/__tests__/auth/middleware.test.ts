import { describe, it, expect } from 'vitest'
import { middleware } from '@/middleware'
import { NextRequest } from 'next/server'

// Build a NextRequest with an optional HttpOnly-style session cookie.
// Middleware runs server-side, so it can read HttpOnly cookies — it does a
// presence check only; the JWT itself is validated by the backend.
function makeRequest(pathname: string, session?: string): NextRequest {
  const url = `http://localhost:3000${pathname}`
  const req = new NextRequest(url)
  if (session) {
    // NextRequest cookies are read-only; set via headers
    const headers = new Headers(req.headers)
    headers.set('cookie', `session=${session}`)
    return new NextRequest(url, { headers })
  }
  return req
}

describe('middleware', () => {
  it('redirects to / when accessing a protected route with no session cookie', () => {
    const req = makeRequest('/dashboard')
    const res = middleware(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toBe('http://localhost:3000/')
  })

  it('passes through when accessing a protected route with a session cookie', () => {
    const req = makeRequest('/dashboard', 'some-session-jwt')
    const res = middleware(req)
    // NextResponse.next() has status 200
    expect(res.status).toBe(200)
  })

  it('passes through when accessing / (public path) with no session cookie', () => {
    const req = makeRequest('/')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('passes through when accessing /auth/callback (public path) with no session cookie', () => {
    const req = makeRequest('/auth/callback')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('passes through when accessing /privacy (public path) with no session cookie', () => {
    const req = makeRequest('/privacy')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('redirects to /dashboard when accessing / with a session cookie', () => {
    const req = makeRequest('/', 'some-session-jwt')
    const res = middleware(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/dashboard')
  })

  it('does not redirect when accessing /privacy with a session cookie', () => {
    const req = makeRequest('/privacy', 'some-session-jwt')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('ignores the legacy JS-set token cookie — only session counts', () => {
    const url = 'http://localhost:3000/dashboard'
    const headers = new Headers()
    headers.set('cookie', 'token=legacy-jwt')
    const req = new NextRequest(url, { headers })
    const res = middleware(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toBe('http://localhost:3000/')
  })
})
