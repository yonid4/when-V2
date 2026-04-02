'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { EventWithParticipants } from '@/types'

const EVENTS_KEY = ['events'] as const
const eventKey = (uid: string) => ['events', uid] as const

export function useEvents() {
  return useQuery({
    queryKey: EVENTS_KEY,
    queryFn: () => api.get<EventWithParticipants[]>('/events'),
  })
}

export function useEvent(uid: string) {
  return useQuery({
    queryKey: eventKey(uid),
    queryFn: () => api.get<EventWithParticipants>(`/events/${uid}`),
    enabled: !!uid,
  })
}

export function useCreateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof api.post>[1]) =>
      api.post<EventWithParticipants>('/events', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: EVENTS_KEY })
    },
  })
}

export function useUpdateEvent(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof api.patch>[1]) =>
      api.patch<EventWithParticipants>(`/events/${uid}`, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(eventKey(uid), updated)
      queryClient.invalidateQueries({ queryKey: EVENTS_KEY })
    },
  })
}

export function useDeleteEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (uid: string) => api.delete<void>(`/events/${uid}`),
    onSuccess: (_data, uid) => {
      queryClient.removeQueries({ queryKey: eventKey(uid) })
      queryClient.invalidateQueries({ queryKey: EVENTS_KEY })
    },
  })
}
