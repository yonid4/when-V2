'use client'

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

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
      return window.localStorage.getItem('token')
    },
  },
})

// Expose for console debugging.
if (typeof window !== 'undefined') {
  ;(window as unknown as { supabase: typeof supabase }).supabase = supabase
}
