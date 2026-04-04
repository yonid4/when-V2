'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { CalendarAccount, CalendarSource } from '@/types'

const ACCOUNTS_KEY = ['calendar-accounts'] as const

export function useCalendarAccounts() {
  return useQuery({
    queryKey: ACCOUNTS_KEY,
    queryFn: () => api.get<CalendarAccount[]>('/calendar-accounts'),
  })
}

export function useDisconnectCalendarAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) =>
      api.delete<void>(`/calendar-accounts/${accountId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY })
    },
  })
}

export function useConnectCalendarAccount() {
  return async () => {
    const data = await api.get<{ url: string }>('/calendar-accounts/connect-url')
    window.location.href = data.url
  }
}

export function useUpdateCalendarSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      sourceId,
      data,
    }: {
      sourceId: string
      data: Partial<Pick<CalendarSource, 'is_enabled' | 'is_write_calendar'>>
    }) => api.patch<CalendarSource>(`/calendar-sources/${sourceId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY })
    },
  })
}
