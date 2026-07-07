'use client'

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

// ─── Short-lived realtime token, held in memory only ─────────────────────────
//
// supabase-js needs a JS-readable JWT to join channels as `authenticated`
// (anon was revoked in the privacy-hardening migration), so realtime is the
// one place a token must exist outside the HttpOnly session cookie. To bound
// the exposure it is a dedicated 1-hour JWT from GET /auth/realtime-token,
// cached in module memory — never localStorage, never a cookie — and refetched
// shortly before expiry. An XSS could steal at most this 1-hour token, not the
// 7-day session credential.

const REFRESH_MARGIN_MS = 60_000

let cachedToken: string | null = null
let cachedExpiresAt = 0 // epoch ms
let inflight: Promise<string | null> | null = null

/** Drop the cached realtime token. Called by the auth store on login/logout so
 * a token minted for one session never leaks into the next. */
export function resetRealtimeTokenCache(): void {
  cachedToken = null
  cachedExpiresAt = 0
  inflight = null
}

async function fetchRealtimeToken(): Promise<string | null> {
  // Raw fetch on purpose: lib/api's 401 handling (clearAuth + redirect) must
  // not fire from a background realtime refresh — an unauthenticated user
  // simply gets no token and channels stay anonymous.
  try {
    const res = await fetch('/api/auth/realtime-token')
    if (!res.ok) {
      resetRealtimeTokenCache()
      return null
    }
    const data = (await res.json()) as { token: string; expires_in: number }
    cachedToken = data.token
    cachedExpiresAt = Date.now() + data.expires_in * 1000
    return cachedToken
  } catch {
    return null
  }
}

async function getRealtimeToken(): Promise<string | null> {
  if (cachedToken && Date.now() < cachedExpiresAt - REFRESH_MARGIN_MS) {
    return cachedToken
  }
  if (!inflight) {
    inflight = fetchRealtimeToken().finally(() => {
      inflight = null
    })
  }
  return inflight
}

/**
 * The `realtime.accessToken` callback is invoked on-demand whenever the
 * Realtime client needs a JWT — at connect time, on every channel join, and
 * after `setAuth()` is called. This avoids races where channels would
 * otherwise subscribe before an async `setAuth(token)` resolves.
 *
 * Required since the May 2026 privacy hardening migration restricted
 * realtime.messages policies from `anon` to `authenticated`. With this
 * callback, every channel join carries the user's JWT, so they connect as
 * the `authenticated` role.
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  realtime: {
    accessToken: async () => {
      if (typeof window === 'undefined') return null
      return getRealtimeToken()
    },
  },
})

// Expose for console debugging.
if (typeof window !== 'undefined') {
  ;(window as unknown as { supabase: typeof supabase }).supabase = supabase
}
