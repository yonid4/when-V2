'use client'

import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import type { User } from '@/types'

interface PresenceUser {
  user_id: string
  avatar_url: string | null
  full_name: string | null
}

/**
 * Wires Supabase real-time postgres_changes subscriptions for an event:
 * - preferred_slots * → invalidate ['preferred-slots', uid]
 * - event_participants * → invalidate ['participants', uid]
 * - events UPDATE → invalidate all event-related query keys
 * - busy_slots * → invalidate ['busy-slots', 'events', uid] (only if currentUserId provided)
 */
export function useEventSubscriptions(
  uid: string,
  eventDbId: string | undefined,
  currentUserId?: string,
) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!uid || !eventDbId) return
    const ch = supabase
      .channel(`event-subs-${uid}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${eventDbId}` },
        () => {
          queryClient.refetchQueries({ queryKey: ['preferred-slots', uid] })
          queryClient.refetchQueries({ queryKey: ['availability-segments', uid] })
        },
      )
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'event_participants', filter: `event_id=eq.${eventDbId}` },
        () => {
          queryClient.refetchQueries({ queryKey: ['participants', uid] })
          queryClient.refetchQueries({ queryKey: ['busy-slots', 'events', uid] })
          queryClient.refetchQueries({ queryKey: ['availability-segments', uid] })
        },
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'events', filter: `id=eq.${eventDbId}` },
        () => {
          queryClient.invalidateQueries({ queryKey: ['events', uid] })
          queryClient.invalidateQueries({ queryKey: ['participants', uid] })
          queryClient.invalidateQueries({ queryKey: ['proposals', uid] })
          queryClient.invalidateQueries({ queryKey: ['preferred-slots', uid] })
          queryClient.refetchQueries({ queryKey: ['availability-segments', uid] })
          queryClient.invalidateQueries({ queryKey: ['busy-slots', 'events', uid] })
          queryClient.invalidateQueries({ queryKey: ['finalize-status', uid] })
        },
      )
      .subscribe()

    return () => {
      supabase.removeChannel(ch)
    }
  }, [uid, eventDbId, queryClient])

  useEffect(() => {
    if (!uid || !currentUserId) return

    const ch = supabase
      .channel(`busy-slots-subs-${uid}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'busy_slots', filter: `user_id=eq.${currentUserId}` },
        () => {
          queryClient.refetchQueries({ queryKey: ['busy-slots', 'events', uid] })
          queryClient.refetchQueries({ queryKey: ['availability-segments', uid] })
        },
      )
      .subscribe()

    return () => {
      supabase.removeChannel(ch)
    }
  }, [uid, currentUserId, queryClient])
}

/**
 * Tracks who else is currently viewing the event via Supabase Presence.
 * Returns the list of present users (excluding the current user).
 */
export function useEventPresence(
  uid: string,
  currentUser: User | null,
): PresenceUser[] {
  const [presentUsers, setPresentUsers] = useState<PresenceUser[]>([])

  useEffect(() => {
    if (!uid || !currentUser) return

    const channel = supabase.channel(`presence-event-${uid}`, {
      config: { presence: { key: currentUser.id } },
    })

    channel
      .on('presence', { event: 'sync' }, () => {
        const state = channel.presenceState<PresenceUser>()
        const users = Object.values(state)
          .flat()
          .filter((u) => u.user_id !== currentUser.id)
        setPresentUsers(users)
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          await channel.track({
            user_id: currentUser.id,
            avatar_url: currentUser.avatar_url,
            full_name: currentUser.full_name,
          })
        }
      })

    return () => {
      supabase.removeChannel(channel)
      setPresentUsers([])
    }
  }, [uid, currentUser])

  return presentUsers
}
