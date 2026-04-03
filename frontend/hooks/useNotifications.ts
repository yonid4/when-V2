'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Notification } from '@/types'

const NOTIFICATIONS_KEY = ['notifications'] as const

export function useNotifications() {
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => api.get<Notification[]>('/notifications'),
  })
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (notificationId: string) =>
      api.post<Notification>(`/notifications/${notificationId}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })
    },
  })
}

export function useTakeAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ notificationId, action }: { notificationId: string; action: 'accept' | 'decline' }) =>
      api.post<Notification>(`/notifications/${notificationId}/action`, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY })
      queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}
