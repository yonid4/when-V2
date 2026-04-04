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
import { useEventBusySlots, useSyncCalendar, useSyncMyCalendar } from '@/hooks/useBusySlots'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return React.createElement(QueryClientProvider, { client: queryClient }, children)
}

const now = new Date().toISOString()
const mockSlot = {
  id: 'slot-1',
  user_id: 'user-1',
  calendar_source_id: 'source-1',
  start_time_utc: now,
  end_time_utc: now,
}

describe('useEventBusySlots', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches busy slots for an event', async () => {
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    const { result } = renderHook(() => useEventBusySlots('event-uid-1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([mockSlot])
    expect(api.get).toHaveBeenCalledWith('/busy-slots/event/event-uid-1')
  })

  it('is disabled when uid is empty', () => {
    const { result } = renderHook(() => useEventBusySlots(''), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('useSyncCalendar', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls sync endpoint for event', async () => {
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    vi.mocked(api.post).mockResolvedValue({ synced: 5 })
    const { result } = renderHook(
      () => ({
        slots: useEventBusySlots('event-uid-1'),
        sync: useSyncCalendar('event-uid-1'),
      }),
      { wrapper }
    )
    result.current.sync.mutate()
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
