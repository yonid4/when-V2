/**
 * Sprint 4 (Post) — NotificationList redirect tests
 *
 * Accept: redirects to /events/{event_uid} after onSuccess
 * Decline: does not redirect
 */
import { render, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const mockPush = vi.fn()
const mockTakeAction = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}))

vi.mock('@/hooks/useNotifications', () => ({
  useNotifications: vi.fn(),
  useMarkRead: () => ({ mutate: vi.fn() }),
  useTakeAction: () => ({ mutate: mockTakeAction, isPending: false }),
}))

vi.mock('date-fns', () => ({
  formatDistanceToNow: () => '1 minute ago',
}))

import { useNotifications } from '@/hooks/useNotifications'
import { NotificationList } from '@/components/notifications/NotificationList'
import type { Notification } from '@/types'

function makeInvite(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'notif-1',
    user_id: 'user-1',
    event_id: 'evt-1',
    event_uid: 'abc-uid',
    notification_type: 'event_invitation',
    title: 'You have been invited',
    message: 'Join the event',
    is_read: false,
    action_taken: false,
    action_type: null,
    metadata: { invitation_id: 'inv-1' },
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

describe('NotificationList — accept/decline redirect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useNotifications).mockReturnValue({ data: [], isLoading: false } as any)
  })

  it('redirects to /events/{event_uid} after accept onSuccess', () => {
    const notification = makeInvite({ id: 'n1', event_uid: 'abc-uid' })
    vi.mocked(useNotifications).mockReturnValue({ data: [notification], isLoading: false } as any)

    const { getByText } = renderWithQuery(<NotificationList />)
    fireEvent.click(getByText('Accept'))

    expect(mockTakeAction).toHaveBeenCalledWith(
      { notificationId: 'n1', action: 'accept' },
      expect.objectContaining({ onSuccess: expect.any(Function) })
    )

    const [, callbacks] = mockTakeAction.mock.calls[0]
    callbacks.onSuccess({ event_uid: 'abc-uid' })

    expect(mockPush).toHaveBeenCalledWith('/events/abc-uid')
  })

  it('redirects to /dashboard when event_uid is null after accept onSuccess', () => {
    const notification = makeInvite({ id: 'n2', event_uid: null })
    vi.mocked(useNotifications).mockReturnValue({ data: [notification], isLoading: false } as any)

    const { getByText } = renderWithQuery(<NotificationList />)
    fireEvent.click(getByText('Accept'))

    const [, callbacks] = mockTakeAction.mock.calls[0]
    callbacks.onSuccess({ event_uid: null })

    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  it('does not redirect after decline', () => {
    const notification = makeInvite({ id: 'n3', event_uid: 'abc-uid' })
    vi.mocked(useNotifications).mockReturnValue({ data: [notification], isLoading: false } as any)

    const { getByText } = renderWithQuery(<NotificationList />)
    fireEvent.click(getByText('Decline'))

    expect(mockTakeAction).toHaveBeenCalledWith({ notificationId: 'n3', action: 'decline' })
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('redirects to /settings?connect_calendar=true on calendar_required error', () => {
    const notification = makeInvite({ id: 'n4', event_uid: 'abc-uid' })
    vi.mocked(useNotifications).mockReturnValue({ data: [notification], isLoading: false } as any)

    const { getByText } = renderWithQuery(<NotificationList />)
    fireEvent.click(getByText('Accept'))

    const [, callbacks] = mockTakeAction.mock.calls[0]
    callbacks.onError(new Error('calendar_required'))

    expect(mockPush).toHaveBeenCalledWith('/settings?connect_calendar=true')
  })
})
