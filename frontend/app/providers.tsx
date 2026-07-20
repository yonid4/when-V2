'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { getBrowserTimezone } from '@/lib/dates'
import { User } from '@/types'

// Keep in sync with PUBLIC_PATHS in middleware.ts. On these paths a visitor
// may legitimately be unauthenticated, so probing /auth/me would just produce
// a guaranteed 401 (and its clearAuth/redirect side effects) for every
// anonymous visitor. Everywhere else, middleware has already verified the
// session cookie exists, so rehydration is expected to succeed.
const PUBLIC_PATHS = ['/', '/auth/callback', '/privacy', '/terms']

function AuthRehydrator() {
  const pathname = usePathname()
  const setUser = useAuthStore((s) => s.setUser)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const user = useAuthStore((s) => s.user)

  useEffect(() => {
    // One-time migration hygiene: purge credentials persisted by the previous
    // localStorage/JS-cookie auth. Any token there is still XSS-readable until
    // removed. Safe to run repeatedly; no-ops once clean.
    localStorage.removeItem('token')
    document.cookie = 'token=; Max-Age=0; path=/'
  }, [])

  useEffect(() => {
    if (user) return
    if (PUBLIC_PATHS.includes(pathname)) return
    // The HttpOnly session cookie (invisible to JS by design) authenticates
    // this call via the /api proxy.
    api.get<User>('/auth/me').then((fetchedUser) => {
      setUser(fetchedUser)
    }).catch(() => {
      clearAuth()
    })
  }, [pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep profiles.timezone aligned with the browser's IANA zone so the chat
  // agent renders slot times as local wall-clock (it defaults to 'UTC'
  // otherwise). Patches only when they differ, so this is a once-per-change
  // write, and self-heals when the user travels.
  useEffect(() => {
    if (!user) return
    const browserTz = getBrowserTimezone()
    if (!browserTz || user.timezone === browserTz) return
    api
      .patch<User>('/account', { timezone: browserTz })
      .then((updatedUser) => setUser(updatedUser))
      .catch(() => {
        /* best-effort — retried on next mount */
      })
  }, [user?.id, user?.timezone]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <AuthRehydrator />
      {children}
    </QueryClientProvider>
  )
}
