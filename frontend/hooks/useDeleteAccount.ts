'use client'

import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useDeleteAccount() {
  return useMutation({
    mutationFn: () => api.delete<void>('/account'),
  })
}
