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
import { usePreferredSlots, useSavePreferredSlot, useDeletePreferredSlot } from '@/hooks/usePreferredSlots'

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

const now = new Date().toISOString()
const mockSlot = {
  id: 'slot-uuid-1',
  event_id: 'event-db-id-1',
  user_id: 'user-uuid-1',
  start_time_utc: '2026-04-10T10:00:00+00:00',
  end_time_utc: '2026-04-10T10:30:00+00:00',
  created_at: now,
}

describe('usePreferredSlots', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches preferred slots from the correct endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    const { result } = renderHook(() => usePreferredSlots('event-uid-1'), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([mockSlot])
    expect(api.get).toHaveBeenCalledWith('/events/event-uid-1/preferred-slots')
  })

  it('is disabled when uid is empty', () => {
    const { result } = renderHook(() => usePreferredSlots(''), { wrapper: makeWrapper() })
    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('useSavePreferredSlot', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts to the correct endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    vi.mocked(api.post).mockResolvedValue(mockSlot)
    const wrapper = makeWrapper()
    const { result } = renderHook(
      () => ({
        save: useSavePreferredSlot('event-uid-1'),
        slots: usePreferredSlots('event-uid-1'),
      }),
      { wrapper }
    )
    result.current.save.mutate({
      start_time_utc: '2026-04-10T10:00:00+00:00',
      end_time_utc: '2026-04-10T10:30:00+00:00',
    })
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/events/event-uid-1/preferred-slots', {
        start_time_utc: '2026-04-10T10:00:00+00:00',
        end_time_utc: '2026-04-10T10:30:00+00:00',
      })
    )
  })

  it('invalidates preferred-slots query on success', async () => {
    vi.mocked(api.post).mockResolvedValue(mockSlot)
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    const wrapper = makeWrapper()
    const { result } = renderHook(
      () => ({
        save: useSavePreferredSlot('event-uid-1'),
        slots: usePreferredSlots('event-uid-1'),
      }),
      { wrapper }
    )
    // Seed the query
    await waitFor(() => expect(result.current.slots.isSuccess).toBe(true))
    const callsBefore = vi.mocked(api.get).mock.calls.length

    result.current.save.mutate({
      start_time_utc: '2026-04-10T10:00:00+00:00',
      end_time_utc: '2026-04-10T10:30:00+00:00',
    })
    await waitFor(() => expect(result.current.save.isSuccess).toBe(true))
    // After mutation, the query should have been invalidated and re-fetched
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(callsBefore))
  })
})

describe('useDeletePreferredSlot', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls delete on the correct endpoint', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    const wrapper = makeWrapper()
    const { result } = renderHook(
      () => ({
        del: useDeletePreferredSlot('event-uid-1'),
        slots: usePreferredSlots('event-uid-1'),
      }),
      { wrapper }
    )
    result.current.del.mutate('slot-uuid-1')
    await waitFor(() =>
      expect(api.delete).toHaveBeenCalledWith('/events/event-uid-1/preferred-slots/slot-uuid-1')
    )
  })

  it('invalidates preferred-slots query on success', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    vi.mocked(api.get).mockResolvedValue([mockSlot])
    const wrapper = makeWrapper()
    const { result } = renderHook(
      () => ({
        del: useDeletePreferredSlot('event-uid-1'),
        slots: usePreferredSlots('event-uid-1'),
      }),
      { wrapper }
    )
    // Seed the query
    await waitFor(() => expect(result.current.slots.isSuccess).toBe(true))
    const callsBefore = vi.mocked(api.get).mock.calls.length

    result.current.del.mutate('slot-uuid-1')
    await waitFor(() => expect(result.current.del.isSuccess).toBe(true))
    // After deletion, the query should have been invalidated and re-fetched
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(callsBefore))
  })
})
