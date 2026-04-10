'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { FinalizeStatus } from '@/types'

interface FinalizeBody {
  proposed_time_id: string
  name: string
  excluded_user_ids: string[]
  extra_emails: string[]
  note: string
  location: string
  video_call_link: string
}

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
