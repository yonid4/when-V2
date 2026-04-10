'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ProposalResponse } from '@/types'

const proposalsKey = (uid: string) => ['proposals', uid] as const

export function useProposals(uid: string, enabled: boolean) {
  return useQuery({
    queryKey: proposalsKey(uid),
    queryFn: () => api.post<ProposalResponse[]>(`/events/${uid}/proposals`, {}),
    enabled: !!uid && enabled,
  })
}

export function useRefreshProposals(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<ProposalResponse[]>(`/events/${uid}/proposals/refresh`, {}),
    onSuccess: (data) => {
      queryClient.setQueryData(proposalsKey(uid), data)
    },
  })
}
