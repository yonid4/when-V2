import type { QueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { EventWithParticipants } from '@/types'

/**
 * Fetches a fresh copy of the event, using the React Query cache when
 * the data is still within its staleTime, or re-fetching when stale.
 */
export function fetchFreshEvent(queryClient: QueryClient, uid: string) {
  return queryClient.fetchQuery<EventWithParticipants>({
    queryKey: ['events', uid],
    queryFn: () => api.get<EventWithParticipants>(`/events/${uid}`),
  })
}
