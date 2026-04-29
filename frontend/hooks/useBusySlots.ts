'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { availabilitySegmentsKey } from './useAvailabilitySegments'

const eventBusySlotsKey = (uid: string) => ['busy-slots', 'event', uid] as const

export function useSyncCalendar(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ synced: number }>(`/busy-slots/sync/event/${uid}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventBusySlotsKey(uid) })
      queryClient.invalidateQueries({ queryKey: availabilitySegmentsKey(uid) })
      queryClient.invalidateQueries({ queryKey: ['calendar-accounts'] })
    },
  })
}

export function useSyncMyCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ synced: number }>('/busy-slots/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['busy-slots'] })
      queryClient.invalidateQueries({ queryKey: ['availability-segments'] })
      queryClient.invalidateQueries({ queryKey: ['calendar-accounts'] })
    },
  })
}
