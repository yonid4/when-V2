'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { User } from '@/types'

function AuthRehydrator() {
  const setUser = useAuthStore((s) => s.setUser)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const user = useAuthStore((s) => s.user)

  useEffect(() => {
    if (user) return
    const token = localStorage.getItem('token')
    if (!token) return
    api.get<User>('/auth/me').then((fetchedUser) => {
      setUser(fetchedUser, token)
    }).catch(() => {
      clearAuth()
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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
