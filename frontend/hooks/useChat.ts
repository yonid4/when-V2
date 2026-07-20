'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { nowUtcIso } from '@/lib/dates'
import type { ChatThread, ChatMessage, ChatTurnRequest, ChatTurnResponse } from '@/types'

const chatThreadsKey = ['chat', 'threads'] as const
const chatMessagesKey = (threadId: string) => ['chat', 'messages', threadId] as const

export function useChatThreads() {
  return useQuery({
    queryKey: chatThreadsKey,
    queryFn: () => api.get<ChatThread[]>('/chat/threads'),
  })
}

export function useChatMessages(threadId: string) {
  return useQuery({
    queryKey: chatMessagesKey(threadId),
    queryFn: () => api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`),
    enabled: !!threadId,
  })
}

export function useCreateChatThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<ChatThread>('/chat/threads'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatThreadsKey })
    },
  })
}

export function useSendChatTurn(threadId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ChatTurnRequest) =>
      api.post<ChatTurnResponse>(`/chat/threads/${threadId}/turn`, body),
    // Show the user's own text the instant they hit send. Structured action
    // turns (button clicks) carry no message — nothing to append for those.
    onMutate: async (body: ChatTurnRequest) => {
      const message = body.message
      if (!message) return { optimisticId: null }
      await queryClient.cancelQueries({ queryKey: chatMessagesKey(threadId) })
      const optimisticId = `optimistic-${Date.now()}`
      queryClient.setQueryData<ChatMessage[]>(chatMessagesKey(threadId), (prev) => [
        ...(prev ?? []),
        {
          id: optimisticId,
          thread_id: threadId,
          role: 'user',
          content: message,
          created_at: nowUtcIso(),
        },
      ])
      return { optimisticId }
    },
    onError: (_err, _body, context) => {
      if (!context?.optimisticId) return
      queryClient.setQueryData<ChatMessage[]>(chatMessagesKey(threadId), (prev) =>
        (prev ?? []).filter((m) => m.id !== context.optimisticId)
      )
    },
    onSuccess: (response, _body, context) => {
      // The turn response includes the persisted user row — replace the
      // optimistic message with the server's copy so it never duplicates.
      queryClient.setQueryData<ChatMessage[]>(chatMessagesKey(threadId), (prev) => [
        ...(prev ?? []).filter((m) => m.id !== context?.optimisticId),
        ...response.messages,
      ])
      queryClient.invalidateQueries({ queryKey: chatThreadsKey })
      if (response.event_uid) {
        queryClient.invalidateQueries({ queryKey: ['events'] })
        queryClient.invalidateQueries({ queryKey: ['events', response.event_uid] })
      }
    },
  })
}

export function useDeleteChatThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (threadId: string) => api.delete<void>(`/chat/threads/${threadId}`),
    onSuccess: (_data, threadId) => {
      queryClient.removeQueries({ queryKey: chatMessagesKey(threadId) })
      queryClient.invalidateQueries({ queryKey: chatThreadsKey })
    },
  })
}
