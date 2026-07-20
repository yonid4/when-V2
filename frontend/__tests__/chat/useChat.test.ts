/**
 * useSendChatTurn optimistic updates + useDeleteChatThread.
 *
 * Covers:
 * - the user's message is appended to the messages cache immediately on send
 * - the optimistic message is replaced by the server rows on success (no dupes)
 * - the optimistic message is rolled back on error
 * - action-only turns (button clicks) append nothing optimistically
 * - deleting a thread hits the endpoint and drops its messages cache
 */
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
import { useSendChatTurn, useDeleteChatThread } from '@/hooks/useChat'
import type { ChatMessage } from '@/types'

const THREAD_ID = 'thread-1'
const messagesKey = ['chat', 'messages', THREAD_ID]

function makeHarness() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
  return { queryClient, wrapper }
}

function serverMessages(): ChatMessage[] {
  return [
    {
      id: 'm-user',
      thread_id: THREAD_ID,
      role: 'user',
      content: 'Find us a time',
      created_at: '2026-07-19T10:00:00Z',
    },
    {
      id: 'm-assistant',
      thread_id: THREAD_ID,
      role: 'assistant',
      content: 'Sure — when works?',
      created_at: '2026-07-19T10:00:05Z',
    },
  ]
}

describe('useSendChatTurn — optimistic user message', () => {
  beforeEach(() => vi.clearAllMocks())

  it('appends the user message to the cache immediately, then swaps in server rows', async () => {
    let resolvePost!: (value: unknown) => void
    vi.mocked(api.post).mockImplementation(
      () => new Promise((resolve) => { resolvePost = resolve })
    )
    const { queryClient, wrapper } = makeHarness()
    queryClient.setQueryData<ChatMessage[]>(messagesKey, [])

    const { result } = renderHook(() => useSendChatTurn(THREAD_ID), { wrapper })
    act(() => result.current.mutate({ message: 'Find us a time', context: { page: 'other' } }))

    // Optimistic: visible before the server responds.
    await waitFor(() => {
      const cached = queryClient.getQueryData<ChatMessage[]>(messagesKey) ?? []
      expect(cached).toHaveLength(1)
      expect(cached[0]).toMatchObject({ role: 'user', content: 'Find us a time' })
      expect(cached[0].id).toMatch(/^optimistic-/)
    })

    act(() => {
      resolvePost({ thread: { id: THREAD_ID }, messages: serverMessages(), event_uid: null })
    })

    // Reconciled: server copies only, no duplicate of the user message.
    await waitFor(() => {
      const cached = queryClient.getQueryData<ChatMessage[]>(messagesKey) ?? []
      expect(cached.map((m) => m.id)).toEqual(['m-user', 'm-assistant'])
    })
  })

  it('rolls the optimistic message back when the turn fails', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('boom'))
    const { queryClient, wrapper } = makeHarness()
    queryClient.setQueryData<ChatMessage[]>(messagesKey, [])

    const { result } = renderHook(() => useSendChatTurn(THREAD_ID), { wrapper })
    act(() => result.current.mutate({ message: 'Find us a time', context: { page: 'other' } }))

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(queryClient.getQueryData<ChatMessage[]>(messagesKey)).toEqual([])
  })

  it('appends nothing optimistically for action-only turns', async () => {
    let resolvePost!: (value: unknown) => void
    vi.mocked(api.post).mockImplementation(
      () => new Promise((resolve) => { resolvePost = resolve })
    )
    const { queryClient, wrapper } = makeHarness()
    queryClient.setQueryData<ChatMessage[]>(messagesKey, [])

    const { result } = renderHook(() => useSendChatTurn(THREAD_ID), { wrapper })
    act(() =>
      result.current.mutate({ action: { type: 'book_direct' }, context: { page: 'other' } })
    )

    await waitFor(() => expect(result.current.isPending).toBe(true))
    expect(queryClient.getQueryData<ChatMessage[]>(messagesKey)).toEqual([])

    act(() => {
      resolvePost({ thread: { id: THREAD_ID }, messages: serverMessages(), event_uid: null })
    })
    await waitFor(() => {
      const cached = queryClient.getQueryData<ChatMessage[]>(messagesKey) ?? []
      expect(cached.map((m) => m.id)).toEqual(['m-user', 'm-assistant'])
    })
  })
})

describe('useDeleteChatThread', () => {
  beforeEach(() => vi.clearAllMocks())

  it('DELETEs the thread and removes its messages cache', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)
    const { queryClient, wrapper } = makeHarness()
    queryClient.setQueryData<ChatMessage[]>(messagesKey, serverMessages())

    const { result } = renderHook(() => useDeleteChatThread(), { wrapper })
    act(() => result.current.mutate(THREAD_ID))

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(api.delete).toHaveBeenCalledWith(`/chat/threads/${THREAD_ID}`)
    expect(queryClient.getQueryData<ChatMessage[]>(messagesKey)).toBeUndefined()
  })
})
