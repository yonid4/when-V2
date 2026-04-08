'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PreferredSlot } from '@/types'

const preferredSlotsKey = (uid: string) => ['preferred-slots', uid] as const

export function usePreferredSlots(uid: string) {
  return useQuery({
    queryKey: preferredSlotsKey(uid),
    queryFn: () => api.get<PreferredSlot[]>(`/events/${uid}/preferred-slots`),
    enabled: !!uid,
  })
}

export function useSavePreferredSlot(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { start_time_utc: string; end_time_utc: string }) =>
      api.post<PreferredSlot>(`/events/${uid}/preferred-slots`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferredSlotsKey(uid) })
    },
  })
}

export function useDeletePreferredSlot(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (slotId: string) =>
      api.delete<void>(`/events/${uid}/preferred-slots/${slotId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferredSlotsKey(uid) })
    },
  })
}
