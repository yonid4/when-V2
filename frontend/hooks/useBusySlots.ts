'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { BusySlot } from '@/types'

const eventBusySlotsKey = (uid: string) => ['busy-slots', 'event', uid] as const

export function useEventBusySlots(uid: string) {
  return useQuery({
    queryKey: eventBusySlotsKey(uid),
    queryFn: () => api.get<BusySlot[]>(`/busy-slots/event/${uid}`),
    enabled: !!uid,
  })
}

export function useSyncCalendar(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ synced: number }>(`/busy-slots/sync/event/${uid}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventBusySlotsKey(uid) })
    },
  })
}

export function useSyncMyCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ synced: number }>('/busy-slots/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['busy-slots'] })
    },
  })
}
