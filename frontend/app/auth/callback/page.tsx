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
    const token = searchParams.get('token')
    if (!token) {
      router.replace('/')
      return
    }

    // Store token first (setUser writes to localStorage + cookie)
    // Then fetch the user profile to populate the store
    localStorage.setItem('token', token)
    // Also set cookie immediately so middleware can read it on redirect
    document.cookie = `token=${token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=Lax`

    api
      .get<User>('/auth/me')
      .then((user) => {
        setUser(user, token)
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
