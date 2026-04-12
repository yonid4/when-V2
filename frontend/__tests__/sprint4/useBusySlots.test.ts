import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '@/lib/api'
import { useSyncCalendar, useSyncMyCalendar } from '@/hooks/useBusySlots'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return React.createElement(QueryClientProvider, { client: queryClient }, children)
}


describe('useSyncCalendar', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls sync endpoint for event', async () => {
    vi.mocked(api.post).mockResolvedValue({ synced: 5 })
    const { result } = renderHook(() => useSyncCalendar('event-uid-1'), { wrapper })
    result.current.mutate()
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/busy-slots/sync/event/event-uid-1')
    )
  })
})

describe('useSyncMyCalendar', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls personal sync endpoint', async () => {
    vi.mocked(api.post).mockResolvedValue({ synced: 3 })
    const { result } = renderHook(() => useSyncMyCalendar(), { wrapper })
    result.current.mutate()
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/busy-slots/sync')
    )
  })
})
