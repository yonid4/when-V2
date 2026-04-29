import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'

export function useNotificationSubscription(userId: string | undefined) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!userId) return

    const channel = supabase
      .channel(`notifications-subs-${userId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'notifications', filter: `user_id=eq.${userId}` },
        () => {
          // Single source of truth: refetch and let NotificationBell's effect
          // recompute the unread count from the server payload. Avoids the
          // double-counting that an optimistic increment + refetch would cause
          // (especially under React StrictMode in dev where effects run twice).
          queryClient.invalidateQueries({ queryKey: ['notifications'] })
        },
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [userId, queryClient])
}
