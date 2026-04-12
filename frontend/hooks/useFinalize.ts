'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { FinalizeStatus, FinalizeBody } from '@/types'

export function useFinalize(uid: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: FinalizeBody) =>
      api.post(`/events/${uid}/finalize`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', uid] })
      queryClient.invalidateQueries({ queryKey: ['proposals', uid] })
    },
  })
}

export function useFinalizeStatus(uid: string) {
  return useQuery<FinalizeStatus>({
    queryKey: ['finalize-status', uid],
    queryFn: () => api.get<FinalizeStatus>(`/events/${uid}/finalize/status`),
    enabled: !!uid,
  })
}
