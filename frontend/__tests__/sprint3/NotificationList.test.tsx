import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NotificationList } from '@/components/notifications/NotificationList'
import type { Notification } from '@/types'

const mockMarkRead = vi.fn()
const mockRespondToInvitation = vi.fn()

vi.mock('@/hooks/useNotifications', () => ({
  useNotifications: vi.fn(),
  useMarkRead: () => ({ mutate: mockMarkRead }),
}))

vi.mock('@/hooks/useInvitations', () => ({
  useRespondToInvitation: () => ({ mutate: mockRespondToInvitation, isPending: false }),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('date-fns', () => ({
  formatDistanceToNow: () => '1 minute ago',
}))

import { useNotifications } from '@/hooks/useNotifications'

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'notif-1',
    user_id: 'user-1',
    event_id: 'evt-1',
    event_uid: null,
    notification_type: 'invite_accepted',
    title: 'Invitation accepted',
    message: 'Bob accepted the invitation.',
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

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('NotificationList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state', () => {
    vi.mocked(useNotifications).mockReturnValue({ data: undefined, isLoading: true } as any)
    renderWithQuery(<NotificationList />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('shows empty state when no notifications', () => {
    vi.mocked(useNotifications).mockReturnValue({ data: [], isLoading: false } as any)
    renderWithQuery(<NotificationList />)
    expect(screen.getByText(/no notifications yet/i)).toBeInTheDocument()
  })

  it('renders notification title and message', () => {
    vi.mocked(useNotifications).mockReturnValue({
      data: [makeNotification({ title: 'You were invited', message: 'Check it out.' })],
      isLoading: false,
    } as any)
    renderWithQuery(<NotificationList />)
    expect(screen.getByText('You were invited')).toBeInTheDocument()
    expect(screen.getByText('Check it out.')).toBeInTheDocument()
  })

  it('shows Accept/Decline buttons for unactioned event_invitation', () => {
    vi.mocked(useNotifications).mockReturnValue({
      data: [makeNotification({ notification_type: 'event_invitation', action_taken: false, metadata: { invitation_id: 'inv-1' } })],
      isLoading: false,
    } as any)
    renderWithQuery(<NotificationList />)
    expect(screen.getByText('Accept')).toBeInTheDocument()
    expect(screen.getByText('Decline')).toBeInTheDocument()
  })

  it('calls respondToInvitation with accept when Accept is clicked', () => {
    vi.mocked(useNotifications).mockReturnValue({
      data: [makeNotification({ id: 'notif-1', notification_type: 'event_invitation', action_taken: false, metadata: { invitation_id: 'inv-1' } })],
      isLoading: false,
    } as any)
    renderWithQuery(<NotificationList />)
    fireEvent.click(screen.getByText('Accept'))
    expect(mockRespondToInvitation).toHaveBeenCalledWith(
      { invitationId: 'inv-1', action: 'accept' },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    )
  })

  it('calls markRead when non-invitation unread notification is clicked', () => {
    vi.mocked(useNotifications).mockReturnValue({
      data: [makeNotification({ id: 'notif-2', notification_type: 'invite_accepted', is_read: false })],
      isLoading: false,
    } as any)
    renderWithQuery(<NotificationList />)
    fireEvent.click(screen.getByText('Invitation accepted'))
    expect(mockMarkRead).toHaveBeenCalledWith('notif-2')
  })

  it('shows Accepted badge when event_invitation is accepted', () => {
    vi.mocked(useNotifications).mockReturnValue({
      data: [makeNotification({ notification_type: 'event_invitation', action_taken: true, action_type: 'accept' })],
      isLoading: false,
    } as any)
    renderWithQuery(<NotificationList />)
    expect(screen.getByText('Accepted')).toBeInTheDocument()
  })
})
