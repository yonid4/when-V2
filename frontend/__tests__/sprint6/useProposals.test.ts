import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '@/lib/api'
import { useProposals, useRefreshProposals } from '@/hooks/useProposals'

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

const mockProposal = {
  id: 'proposal-uuid-1',
  event_id: 'event-db-id-1',
  start_time_utc: '2026-04-10T09:00:00+00:00',
  end_time_utc: '2026-04-10T10:00:00+00:00',
  conflict_count: 0,
  preferred_count: 1,
  reasoning: '2/2 participants free, 1 marked as preferred',
  rank: 1,
}

describe('useProposals', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches proposals via POST to the correct endpoint when enabled', async () => {
    vi.mocked(api.post).mockResolvedValue([mockProposal])
    const { result } = renderHook(() => useProposals('event-uid-1', true), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([mockProposal])
    expect(api.post).toHaveBeenCalledWith('/events/event-uid-1/proposals', {})
  })

  it('does not fetch when enabled is false', () => {
    const { result } = renderHook(() => useProposals('event-uid-1', false), { wrapper: makeWrapper() })
    expect(result.current.fetchStatus).toBe('idle')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('does not fetch when uid is empty', () => {
    const { result } = renderHook(() => useProposals('', true), { wrapper: makeWrapper() })
    expect(result.current.fetchStatus).toBe('idle')
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('useRefreshProposals', () => {
  beforeEach(() => vi.clearAllMocks())

  it('POSTs to the refresh endpoint and updates cached proposals on success', async () => {
    vi.mocked(api.post).mockResolvedValueOnce([mockProposal]) // initial fetch
    vi.mocked(api.post).mockResolvedValueOnce([{ ...mockProposal, rank: 1 }]) // refresh

    const wrapper = makeWrapper()
    const { result } = renderHook(
      () => ({
        proposals: useProposals('event-uid-1', true),
        refresh: useRefreshProposals('event-uid-1'),
      }),
      { wrapper }
    )

    await waitFor(() => expect(result.current.proposals.isSuccess).toBe(true))

    result.current.refresh.mutate()
    await waitFor(() => expect(result.current.refresh.isSuccess).toBe(true))

    expect(api.post).toHaveBeenCalledWith('/events/event-uid-1/proposals/refresh', {})
  })
})
