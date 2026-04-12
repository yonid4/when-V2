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
 * Wires the three remaining Supabase real-time subscriptions for an event:
 * - busy_slots INSERT → invalidate ['busy-slots', 'event', uid]
 * - event_participants INSERT → invalidate ['participants', uid]
 *
 * The events UPDATE subscription lives in EventDetailClient because it needs
 * access to event.id (DB integer PK) which is available in that component.
 */
export function useEventSubscriptions(
  uid: string,
  eventDbId: string | undefined,
) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!uid || !eventDbId) return

    const busySlotsChannel = supabase
      .channel(`busy-slots-event-${eventDbId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'busy_slots',
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['busy-slots', 'event', uid] })
        }
      )
      .subscribe()

    const participantsChannel = supabase
      .channel(`event-participants-${eventDbId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'event_participants',
          filter: `event_id=eq.${eventDbId}`,
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['participants', uid] })
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(busySlotsChannel)
      supabase.removeChannel(participantsChannel)
    }
  }, [uid, eventDbId, queryClient])
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
