'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Invitation } from '@/types'

export function useInvite(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) =>
      api.post<Invitation>(`/events/${uid}/invite`, { email }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participants', uid] })
    },
  })
}

export function useRespondToInvitation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ invitationId, action }: { invitationId: string; action: 'accept' | 'decline' }) =>
      api.put<{ event_uid: string | null }>(`/invitations/${invitationId}/respond`, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: ['participants'] })
    },
  })
}
