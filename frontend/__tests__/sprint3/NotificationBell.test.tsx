import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NotificationBell } from '@/components/notifications/NotificationBell'

const mockIncrement = vi.fn()
const mockReset = vi.fn()
const mockSetCount = vi.fn()

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
      subscribe: vi.fn().mockReturnValue({ subscribe: vi.fn() }),
    })),
    removeChannel: vi.fn(),
  },
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: vi.fn(() => ({ data: [], isLoading: false })),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock('@/components/notifications/NotificationList', () => ({
  NotificationList: () => <div>Notification List</div>,
}))

// Mock Popover to render children directly
vi.mock('@/components/ui/popover', () => ({
  Popover: ({ children }: any) => <div>{children}</div>,
  PopoverTrigger: ({ children }: any) => <div>{children}</div>,
  PopoverContent: ({ children }: any) => <div>{children}</div>,
}))

import { useNotificationStore } from '@/stores/notificationStore'
import { useAuthStore } from '@/stores/authStore'

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useNotificationStore).mockReturnValue({
      unreadCount: 0,
      increment: mockIncrement,
      reset: mockReset,
      setCount: mockSetCount,
    } as any)
    vi.mocked(useAuthStore).mockReturnValue({ id: 'user-1', email_address: 'alice@example.com' } as any)
  })

  it('renders the bell button', () => {
    render(<NotificationBell />)
    // The bell icon is rendered inside a button
    const button = screen.getByRole('button')
    expect(button).toBeInTheDocument()
  })

  it('does not show badge when unreadCount is 0', () => {
    render(<NotificationBell />)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('shows unread badge when unreadCount > 0', () => {
    vi.mocked(useNotificationStore).mockReturnValue({
      unreadCount: 3,
      increment: mockIncrement,
      reset: mockReset,
      setCount: mockSetCount,
    } as any)
    render(<NotificationBell />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows 99+ when unreadCount exceeds 99', () => {
    vi.mocked(useNotificationStore).mockReturnValue({
      unreadCount: 150,
      increment: mockIncrement,
      reset: mockReset,
      setCount: mockSetCount,
    } as any)
    render(<NotificationBell />)
    expect(screen.getByText('99+')).toBeInTheDocument()
  })

  it('renders NotificationList inside popover content', () => {
    render(<NotificationBell />)
    expect(screen.getByText('Notification List')).toBeInTheDocument()
  })
})
