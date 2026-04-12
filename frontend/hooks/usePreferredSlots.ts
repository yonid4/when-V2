'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PreferredSlot } from '@/types'
import { availabilitySegmentsKey } from './useAvailabilitySegments'

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
    onMutate: async (newSlot) => {
      await queryClient.cancelQueries({ queryKey: preferredSlotsKey(uid) })
      const previous = queryClient.getQueryData<PreferredSlot[]>(preferredSlotsKey(uid))
      const optimistic: PreferredSlot = {
        id: `optimistic-${Date.now()}`,
        user_id: '',
        event_id: '',
        start_time_utc: newSlot.start_time_utc,
        end_time_utc: newSlot.end_time_utc,
        created_at: new Date().toISOString(),
      }
      queryClient.setQueryData<PreferredSlot[]>(preferredSlotsKey(uid), (old) =>
        old ? [...old, optimistic] : [optimistic]
      )
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(preferredSlotsKey(uid), context.previous)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferredSlotsKey(uid) })
      queryClient.invalidateQueries({ queryKey: availabilitySegmentsKey(uid) })
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
      queryClient.invalidateQueries({ queryKey: availabilitySegmentsKey(uid) })
    },
  })
}
