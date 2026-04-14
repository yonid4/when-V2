'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ProposedTimeNote } from '@/types'

const proposalNotesKey = (proposedTimeId: string) => ['proposalNotes', proposedTimeId] as const

export function useProposalNotes(eventUid: string, proposedTimeId: string) {
  const { data: notes, isLoading, error } = useQuery({
    queryKey: proposalNotesKey(proposedTimeId),
    queryFn: () => api.get<ProposedTimeNote[]>(`/events/${eventUid}/proposals/${proposedTimeId}/notes`),
    enabled: !!eventUid && !!proposedTimeId,
  })
  return { notes, isLoading, error }
}

export function useCreateProposalNote(eventUid: string, proposedTimeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string }) =>
      api.post<ProposedTimeNote>(`/events/${eventUid}/proposals/${proposedTimeId}/notes`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: proposalNotesKey(proposedTimeId) })
    },
  })
}

export function useDeleteProposalNote(eventUid: string, proposedTimeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (noteId: string) =>
      api.delete<void>(`/events/${eventUid}/proposals/${proposedTimeId}/notes/${noteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: proposalNotesKey(proposedTimeId) })
    },
  })
}
