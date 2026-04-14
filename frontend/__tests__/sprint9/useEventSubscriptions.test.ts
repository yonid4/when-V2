import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

vi.mock('@/lib/supabase', () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    })),
    removeChannel: vi.fn(),
  },
}))

import { supabase } from '@/lib/supabase'
import { useEventSubscriptions, useEventPresence } from '@/hooks/useEventSubscriptions'
import type { User } from '@/types'

const mockUser: User = {
  id: 'user-1',
  full_name: 'Alice',
  avatar_url: 'https://example.com/avatar.jpg',
  email_address: 'alice@example.com',
}

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

describe('useEventSubscriptions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('subscribes to event-subs channel on mount', () => {
    renderHook(() => useEventSubscriptions('event-uid-1', 'db-id-1'), {
      wrapper: makeWrapper(),
    })

    expect(supabase.channel).toHaveBeenCalledWith('event-subs-event-uid-1')
  })

  it('does not subscribe when eventDbId is undefined', () => {
    renderHook(() => useEventSubscriptions('event-uid-1', undefined), {
      wrapper: makeWrapper(),
    })

    expect(supabase.channel).not.toHaveBeenCalled()
  })

  it('calls removeChannel once (for event-subs channel) on unmount', () => {
    const fakeChannel = {
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const { unmount } = renderHook(() => useEventSubscriptions('event-uid-1', 'db-id-1'), {
      wrapper: makeWrapper(),
    })
    unmount()

    expect(supabase.removeChannel).toHaveBeenCalledTimes(1)
    expect(supabase.removeChannel).toHaveBeenCalledWith(fakeChannel)
  })

  it('calls removeChannel for both channels on unmount when currentUserId is provided', () => {
    const fakeChannel = {
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const { unmount } = renderHook(() => useEventSubscriptions('event-uid-1', 'db-id-1', 'user-1'), {
      wrapper: makeWrapper(),
    })
    unmount()

    expect(supabase.removeChannel).toHaveBeenCalledTimes(2)
    expect(supabase.removeChannel).toHaveBeenCalledWith(fakeChannel)
  })

  it('refetches participants query on event_participants change', () => {
    let participantsCallback: (() => void) | undefined
    const fakeChannel = {
      on: vi.fn((type: string, filter: unknown, cb: () => void) => {
        if (
          type === 'postgres_changes' &&
          typeof filter === 'object' &&
          filter !== null &&
          (filter as Record<string, unknown>).table === 'event_participants'
        ) {
          participantsCallback = cb
        }
        return fakeChannel
      }),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const refetchSpy = vi.spyOn(queryClient, 'refetchQueries')

    renderHook(() => useEventSubscriptions('event-uid-1', 'db-id-1'), {
      wrapper: ({ children }) =>
        React.createElement(QueryClientProvider, { client: queryClient }, children),
    })

    act(() => { participantsCallback?.() })

    expect(refetchSpy).toHaveBeenCalledWith({
      queryKey: ['participants', 'event-uid-1'],
    })
  })

  it('refetches busy-slots query on event_participants change', () => {
    let participantsCallback: (() => void) | undefined
    const fakeChannel = {
      on: vi.fn((type: string, filter: unknown, cb: () => void) => {
        if (
          type === 'postgres_changes' &&
          typeof filter === 'object' &&
          filter !== null &&
          (filter as Record<string, unknown>).table === 'event_participants'
        ) {
          participantsCallback = cb
        }
        return fakeChannel
      }),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const refetchSpy = vi.spyOn(queryClient, 'refetchQueries')

    renderHook(() => useEventSubscriptions('event-uid-1', 'db-id-1'), {
      wrapper: ({ children }) =>
        React.createElement(QueryClientProvider, { client: queryClient }, children),
    })

    act(() => { participantsCallback?.() })

    expect(refetchSpy).toHaveBeenCalledWith({
      queryKey: ['busy-slots', 'events', 'event-uid-1'],
    })
  })
})

describe('useEventPresence', () => {
  beforeEach(() => vi.clearAllMocks())

  it('returns empty array when currentUser is null', () => {
    const { result } = renderHook(() => useEventPresence('event-uid-1', null))
    expect(result.current).toEqual([])
    expect(supabase.channel).not.toHaveBeenCalled()
  })

  it('subscribes to presence channel with uid', () => {
    const fakeChannel = {
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    renderHook(() => useEventPresence('event-uid-1', mockUser))

    expect(supabase.channel).toHaveBeenCalledWith(
      'presence-event-event-uid-1',
      expect.objectContaining({ config: { presence: { key: mockUser.id } } })
    )
  })

  it('tracks current user after SUBSCRIBED', async () => {
    let subscribeCallback: ((status: string) => Promise<void>) | undefined
    const fakeChannel = {
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn((cb: (status: string) => Promise<void>) => {
        subscribeCallback = cb
        return fakeChannel
      }),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    renderHook(() => useEventPresence('event-uid-1', mockUser))

    await act(async () => {
      await subscribeCallback?.('SUBSCRIBED')
    })

    expect(fakeChannel.track).toHaveBeenCalledWith({
      user_id: mockUser.id,
      avatar_url: mockUser.avatar_url,
      full_name: mockUser.full_name,
    })
  })

  it('filters out the current user from presence state', () => {
    let syncCallback: (() => void) | undefined
    const presenceState = {
      [mockUser.id]: [{ user_id: mockUser.id, avatar_url: null, full_name: 'Alice' }],
      'user-2': [{ user_id: 'user-2', avatar_url: null, full_name: 'Bob' }],
    }
    const fakeChannel = {
      on: vi.fn((type: string, _filter: unknown, cb: () => void) => {
        if (type === 'presence') syncCallback = cb
        return fakeChannel
      }),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue(presenceState),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const { result } = renderHook(() => useEventPresence('event-uid-1', mockUser))

    act(() => { syncCallback?.() })

    expect(result.current).toHaveLength(1)
    expect(result.current[0].user_id).toBe('user-2')
  })

  it('calls removeChannel on unmount', () => {
    const fakeChannel = {
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      presenceState: vi.fn().mockReturnValue({}),
      track: vi.fn().mockResolvedValue(undefined),
    }
    vi.mocked(supabase.channel).mockReturnValue(fakeChannel as ReturnType<typeof supabase.channel>)

    const { unmount } = renderHook(() => useEventPresence('event-uid-1', mockUser))
    unmount()

    expect(supabase.removeChannel).toHaveBeenCalledWith(fakeChannel)
  })
})
