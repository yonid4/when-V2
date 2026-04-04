'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Participant } from '@/types'

const participantsKey = (uid: string) => ['participants', uid] as const

export function useParticipants(uid: string) {
  return useQuery({
    queryKey: participantsKey(uid),
    queryFn: () => api.get<Participant[]>(`/events/${uid}/participants`),
    enabled: !!uid,
  })
}

export function useUpdateRsvp(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, rsvp_status }: { userId: string; rsvp_status: string }) =>
      api.put<Participant>(`/events/${uid}/participants/${userId}/rsvp`, { rsvp_status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: participantsKey(uid) })
    },
  })
}

export function useUpdatePermissions(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, can_invite }: { userId: string; can_invite: boolean }) =>
      api.put<Participant>(`/events/${uid}/participants/${userId}/permissions`, { can_invite }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: participantsKey(uid) })
    },
  })
}

export function useRemoveParticipant(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => api.delete<void>(`/events/${uid}/participants/${userId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: participantsKey(uid) })
    },
  })
}
