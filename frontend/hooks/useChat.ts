'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
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
    onSuccess: (response) => {
      queryClient.setQueryData<ChatMessage[]>(chatMessagesKey(threadId), (prev) => [
        ...(prev ?? []),
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
