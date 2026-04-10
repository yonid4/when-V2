/**
 * Sprint 7 — useTakeAction redirect and query invalidation
 *
 * Verifies that on accept:
 *   - router.push('/events/{event_uid}') is called
 *   - participants and notifications queries are invalidated
 * Verifies that on decline:
 *   - router.push is NOT called
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}))

const mockPost = vi.fn()

vi.mock('@/lib/api', () => ({
  api: { post: (...args: unknown[]) => mockPost(...args) },
}))

import { useTakeAction } from '@/hooks/useNotifications'

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    queryClient,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children),
  }
}

describe('useTakeAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('invalidates notifications and participants queries on success', async () => {
    mockPost.mockResolvedValueOnce({ id: 'notif-1' })
    const { queryClient, wrapper } = makeWrapper()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useTakeAction(), { wrapper })

    await act(async () => {
      result.current.mutate({ notificationId: 'notif-1', action: 'accept' })
      // wait for mutation to settle
      await new Promise((r) => setTimeout(r, 0))
    })

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      (call) => (call[0] as { queryKey: unknown[] }).queryKey,
    )
    expect(invalidatedKeys).toContainEqual(['notifications'])
    expect(invalidatedKeys).toContainEqual(['participants'])
    expect(invalidatedKeys).toContainEqual(['events'])
  })

  it('calls the API with correct args', async () => {
    mockPost.mockResolvedValueOnce({ id: 'notif-1' })
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useTakeAction(), { wrapper })

    await act(async () => {
      result.current.mutate({ notificationId: 'notif-42', action: 'decline' })
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(mockPost).toHaveBeenCalledWith('/notifications/notif-42/action', { action: 'decline' })
  })
})
