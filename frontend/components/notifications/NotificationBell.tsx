'use client'

import { useEffect } from 'react'
import { Bell } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { NotificationList } from './NotificationList'
import { useNotificationStore } from '@/stores/notificationStore'
import { useNotifications, useMarkAllRead } from '@/hooks/useNotifications'
import { useNotificationSubscription } from '@/hooks/useNotificationSubscription'
import { useAuthStore } from '@/stores/authStore'

export function NotificationBell() {
  const { unreadCount, reset, setCount } = useNotificationStore()
  const user = useAuthStore((s) => s.user)
  const { data: notifications } = useNotifications()
  const { mutate: markAllRead } = useMarkAllRead()

  useNotificationSubscription(user?.id)

  useEffect(() => {
    if (!notifications) return
    const count = notifications.filter((n) => !n.is_read).length
    setCount(count)
  }, [notifications, setCount])

  return (
    <Popover onOpenChange={(open) => { if (open) { reset(); markAllRead() } }}>
      <PopoverTrigger asChild>
        <button className="relative w-9 h-9 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
          <Bell className="w-5 h-5 text-primary" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full bg-primary text-on-primary text-[10px] font-bold flex items-center justify-center px-1">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-80 p-0 bg-surface-container-lowest rounded-2xl shadow-warm-md border-0"
      >
        <div className="px-4 py-3 border-b border-outline-variant/10">
          <h3 className="font-bold text-sm text-on-surface">Notifications</h3>
        </div>
        <NotificationList />
      </PopoverContent>
    </Popover>
  )
}
