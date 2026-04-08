/**
 * Sprint 4 (Post) — NotificationBell deferred tests
 *
 * Focused test: on mount, when the notifications query resolves, unread count is
 * initialized to the count of notifications where is_read === false.
 */
import { render } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn(),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
    })),
    removeChannel: vi.fn(),
  },
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: vi.fn(),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock('@/hooks/useNotifications', () => ({
  useNotifications: vi.fn(),
  useMarkAllRead: () => ({ mutate: vi.fn() }),
}))

vi.mock('@/components/notifications/NotificationList', () => ({
  NotificationList: () => <div>Notification List</div>,
}))

vi.mock('@/components/ui/popover', () => ({
  Popover: ({ children }: any) => <div>{children}</div>,
  PopoverTrigger: ({ children }: any) => <div>{children}</div>,
  PopoverContent: ({ children }: any) => <div>{children}</div>,
}))

import { useNotificationStore } from '@/stores/notificationStore'
import { useAuthStore } from '@/stores/authStore'
import { useNotifications } from '@/hooks/useNotifications'
import { NotificationBell } from '@/components/notifications/NotificationBell'
import type { Notification } from '@/types'

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'notif-1',
    user_id: 'user-1',
    event_id: 'evt-1',
    notification_type: 'invite_accepted',
    title: 'Test notification',
    message: 'Test message',
    is_read: false,
    action_taken: false,
    action_type: null,
    metadata: null,
    created_at: new Date().toISOString(),
    read_at: null,
    action_at: null,
    ...overrides,
  }
}

describe('NotificationBell — unread count initialization', () => {
  const mockSetCount = vi.fn()
  const mockIncrement = vi.fn()
  const mockReset = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuthStore).mockReturnValue({ id: 'user-1', email_address: 'alice@example.com' } as any)
    vi.mocked(useNotificationStore).mockReturnValue({
      unreadCount: 0,
      increment: mockIncrement,
      reset: mockReset,
      setCount: mockSetCount,
    } as any)
  })

  it('calls setCount with the number of unread notifications when query resolves', () => {
    const notifications = [
      makeNotification({ id: 'n1', is_read: false }),
      makeNotification({ id: 'n2', is_read: true }),
      makeNotification({ id: 'n3', is_read: false }),
    ]
    vi.mocked(useNotifications).mockReturnValue({ data: notifications, isLoading: false } as any)

    render(<NotificationBell />)

    // useEffect fires after render; setCount should be called with 2 (the two unread)
    expect(mockSetCount).toHaveBeenCalledWith(2)
  })

  it('calls setCount(0) when all notifications are read', () => {
    const notifications = [
      makeNotification({ id: 'n1', is_read: true }),
      makeNotification({ id: 'n2', is_read: true }),
    ]
    vi.mocked(useNotifications).mockReturnValue({ data: notifications, isLoading: false } as any)

    render(<NotificationBell />)

    expect(mockSetCount).toHaveBeenCalledWith(0)
  })

  it('does not call setCount when notifications are still loading (undefined)', () => {
    vi.mocked(useNotifications).mockReturnValue({ data: undefined, isLoading: true } as any)

    render(<NotificationBell />)

    // The useEffect guards on `if (!notifications) return`
    expect(mockSetCount).not.toHaveBeenCalled()
  })
})
