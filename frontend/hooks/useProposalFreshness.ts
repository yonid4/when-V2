'use client'

import { useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useRefreshProposals } from './useProposals'
import { fetchFreshEvent } from '@/app/events/[uid]/proposalUtils'

/**
 * Encapsulates the lazy freshness check performed at two points:
 *  1. Before showing the proposal list ("View Proposed Times")
 *  2. Before opening FinalizeCard ("Finalize Event")
 *
 * Returns:
 *  - isChecking: true while the event re-fetch (and optional refresh) is in flight
 *  - checkAndRefreshIfNeeded: call this before showing proposals or finalizing.
 *    Resolves to true when it's safe to proceed, false if it had to refresh
 *    (caller can decide to gate on this, but proposals will already be up-to-date).
 */
export function useProposalFreshness(uid: string) {
  const queryClient = useQueryClient()
  const { mutateAsync: refreshProposalsAsync, isPending: isRefreshing } = useRefreshProposals(uid)
  const [isChecking, setIsChecking] = useState(false)

  const checkAndRefreshIfNeeded = useCallback(async (): Promise<boolean> => {
    setIsChecking(true)
    try {
      const freshEvent = await fetchFreshEvent(queryClient, uid)
      if (freshEvent.proposals_needs_regeneration) {
        await refreshProposalsAsync()
        queryClient.invalidateQueries({ queryKey: ['event', uid] })
        return false
      }
      return true
    } finally {
      setIsChecking(false)
    }
  }, [queryClient, uid, refreshProposalsAsync])

  return { isChecking: isChecking || isRefreshing, checkAndRefreshIfNeeded }
}
