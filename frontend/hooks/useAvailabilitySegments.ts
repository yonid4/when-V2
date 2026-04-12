'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { AvailabilitySegment } from '@/types'

export const availabilitySegmentsKey = (uid: string) => ['availability-segments', uid] as const

export function useAvailabilitySegments(uid: string) {
  return useQuery({
    queryKey: availabilitySegmentsKey(uid),
    queryFn: () => api.get<AvailabilitySegment[]>(`/events/${uid}/availability-segments`),
    enabled: !!uid,
    staleTime: 60_000,
  })
}
