'use client'

import { useAuthStore } from '@/stores/authStore'

const API_BASE = '/api'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function request<T>(method: HttpMethod, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // Auth rides on the HttpOnly `session` cookie, sent automatically on these
  // same-origin requests and forwarded to the backend by the /api proxy. No
  // token ever touches JavaScript here.
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    useAuthStore.getState().clearAuth()
    if (window.location.pathname !== '/') {
      window.location.href = '/'
    }
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }))
    const detail = error.detail ?? 'Request failed'
    const err = new Error(detail) as Error & { detail?: string }
    err.detail = detail
    throw err
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

/**
 * Fire-and-forget logout — clears the HttpOnly session cookie server-side.
 *
 * Deliberately not `request()`: `keepalive` lets the call outlive the page
 * navigation that typically follows clearAuth(), so a stale session cookie is
 * reliably cleared (otherwise middleware's cookie-presence check and an
 * expired token's 401s can redirect-loop). Never throws.
 */
export function logout(): Promise<void> {
  return fetch(`${API_BASE}/auth/logout`, { method: 'POST', keepalive: true })
    .then(() => undefined)
    .catch(() => undefined)
}
