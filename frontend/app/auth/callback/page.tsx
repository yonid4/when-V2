'use client'

export const dynamic = 'force-dynamic'

import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { User } from '@/types'

export default function AuthCallbackPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((s) => s.setUser)

  useEffect(() => {
    // The backend redirects here with a short-lived signed login code — never
    // the session JWT. Exchanging it through the same-origin /api proxy lets
    // the backend set the HttpOnly `session` cookie on this origin; no token
    // ever touches JavaScript, localStorage, or a JS-readable cookie.
    const code = searchParams.get('code')
    if (!code) {
      router.replace('/')
      return
    }

    api
      .post<User>('/auth/session/exchange', { code })
      .then((user) => {
        setUser(user)
        router.replace('/dashboard')
      })
      .catch(() => {
        router.replace('/')
      })
  }, [searchParams, router, setUser])

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Signing you in…</p>
    </main>
  )
}
