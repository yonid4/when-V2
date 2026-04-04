'use client'

import { useRouter } from 'next/navigation'
import { formatDistanceToNow } from 'date-fns'
import { useNotifications, useMarkRead, useTakeAction } from '@/hooks/useNotifications'
import type { Notification } from '@/types'

export function NotificationList() {
  const router = useRouter()
  const { data: notifications, isLoading } = useNotifications()
  const { mutate: markRead } = useMarkRead()
  const { mutate: takeAction, isPending: isActing } = useTakeAction()

  if (isLoading) {
    return <div className="p-4 text-sm text-on-surface-variant">Loading…</div>
  }

  if (!notifications || notifications.length === 0) {
    return <div className="p-4 text-sm text-on-surface-variant text-center">No notifications yet.</div>
  }

  return (
    <div className="flex flex-col divide-y divide-outline-variant/10 max-h-[400px] overflow-y-auto">
      {notifications.map((n: Notification) => (
        <div
          key={n.id}
          onClick={() => {
            if (n.notification_type !== 'event_invitation' && !n.is_read) {
              markRead(n.id)
            }
          }}
          className={`p-4 flex flex-col gap-2 transition-colors cursor-pointer hover:bg-surface-container ${
            !n.is_read ? 'bg-primary-fixed/20' : ''
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-on-surface">{n.title}</p>
              <p className="text-xs text-on-surface-variant mt-0.5">{n.message}</p>
            </div>
            <span className="text-[10px] text-on-surface-variant shrink-0">
              {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
            </span>
          </div>

          {n.notification_type === 'event_invitation' && !n.action_taken && (
            <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => takeAction(
                  { notificationId: n.id, action: 'accept' },
                  {
                    onSuccess: () => {
                      const dest = n.event_uid ? `/events/${n.event_uid}` : '/dashboard'
                      router.push(dest)
                    },
                    onError: (err) => {
                      if (err.message === 'calendar_required') {
                        router.push('/settings?connect_calendar=true')
                      }
                    },
                  }
                )}
                disabled={isActing}
                className="flex-1 py-1.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-on-primary text-xs font-bold disabled:opacity-60 transition-opacity"
              >
                Accept
              </button>
              <button
                onClick={() => takeAction({ notificationId: n.id, action: 'decline' })}
                disabled={isActing}
                className="flex-1 py-1.5 rounded-lg bg-surface-container-high text-on-surface-variant text-xs font-bold disabled:opacity-60 transition-opacity hover:bg-surface-container-highest"
              >
                Decline
              </button>
            </div>
          )}

          {n.notification_type === 'event_invitation' && n.action_taken && (
            <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full self-start ${
              n.action_type === 'accept'
                ? 'bg-secondary-container text-on-secondary-container'
                : 'bg-surface-container-high text-on-surface-variant'
            }`}>
              {n.action_type === 'accept' ? 'Accepted' : 'Declined'}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
