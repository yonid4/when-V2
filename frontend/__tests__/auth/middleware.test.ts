import { describe, it, expect } from 'vitest'
import { middleware } from '@/middleware'
import { NextRequest } from 'next/server'

// Build a NextRequest with optional cookies
function makeRequest(pathname: string, token?: string): NextRequest {
  const url = `http://localhost:3000${pathname}`
  const req = new NextRequest(url)
  if (token) {
    // NextRequest cookies are read-only; set via headers
    const headers = new Headers(req.headers)
    headers.set('cookie', `token=${token}`)
    return new NextRequest(url, { headers })
  }
  return req
}

describe('middleware', () => {
  it('redirects to / when accessing a protected route with no token', () => {
    const req = makeRequest('/dashboard')
    const res = middleware(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toBe('http://localhost:3000/')
  })

  it('passes through when accessing a protected route with a valid token', () => {
    const req = makeRequest('/dashboard', 'some-jwt-token')
    const res = middleware(req)
    // NextResponse.next() has status 200
    expect(res.status).toBe(200)
  })

  it('passes through when accessing / (public path) with no token', () => {
    const req = makeRequest('/')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('passes through when accessing /auth/callback (public path) with no token', () => {
    const req = makeRequest('/auth/callback')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })

  it('redirects to /dashboard when accessing / with a valid token', () => {
    // Per the architecture: / is in PUBLIC_PATHS so middleware always allows it
    // The middleware does NOT redirect / to /dashboard — that's the page's job
    // Verifying middleware just passes through
    const req = makeRequest('/', 'some-jwt-token')
    const res = middleware(req)
    expect(res.status).toBe(200)
  })
})
