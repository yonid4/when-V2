import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
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
import { useFinalize, useFinalizeStatus } from '@/hooks/useFinalize'

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

const mockFinalizeStatus = {
  status: 'confirmed',
  finalized_start_time_utc: '2026-04-10T12:00:00+00:00',
  finalized_end_time_utc: '2026-04-10T13:00:00+00:00',
  google_calendar_event_id: 'gcal-event-123',
}

describe('useFinalize', () => {
  beforeEach(() => vi.clearAllMocks())

  it('POSTs to the correct finalize endpoint with proposed_time_id and note', async () => {
    vi.mocked(api.post).mockResolvedValue({ status: 'confirmed' })

    const { result } = renderHook(() => useFinalize('event-uid-1'), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ proposed_time_id: 'pt-uuid-1', note: 'See you there!' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(api.post).toHaveBeenCalledWith('/events/event-uid-1/finalize', {
      proposed_time_id: 'pt-uuid-1',
      note: 'See you there!',
    })
  })
})

describe('useFinalizeStatus', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches finalize status via GET from the correct endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue(mockFinalizeStatus)

    const { result } = renderHook(() => useFinalizeStatus('event-uid-1'), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(mockFinalizeStatus)
    expect(api.get).toHaveBeenCalledWith('/events/event-uid-1/finalize/status')
  })

  it('does not fetch when uid is empty', () => {
    const { result } = renderHook(() => useFinalizeStatus(''), { wrapper: makeWrapper() })
    expect(result.current.fetchStatus).toBe('idle')
    expect(api.get).not.toHaveBeenCalled()
  })
})
