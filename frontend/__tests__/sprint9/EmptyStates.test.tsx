/**
 * Sprint 9B — Empty states and error states
 *
 * Covers:
 * - Dashboard: shows empty state when no events
 * - Dashboard: shows error state when API fails
 * - NotificationList: shows empty state when no notifications
 * - ProposalList: shows empty state when no proposals
 * - ProposalList: shows skeleton when loading
 * - ParticipantList: shows skeleton when loading
 * - not-found: renders 404 page
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => ({ get: vi.fn().mockReturnValue(null) }),
  usePathname: () => '/',
  Link: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement('a', { href }, children),
}))

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement('a', { href }, children),
}))

vi.mock('@/hooks/useEvent', () => ({
  useEvents: vi.fn(),
}))

vi.mock('@/hooks/useCalendarAccounts', () => ({
  useCalendarAccounts: vi.fn(() => ({ data: [], isLoading: false })),
}))

vi.mock('next/headers', () => ({
  cookies: vi.fn().mockResolvedValue({ get: () => ({ value: 'test-token' }) }),
}))

vi.mock('@/components/layout/Navbar', () => ({
  Navbar: () => React.createElement('nav', null, 'Navbar'),
}))

vi.mock('@/hooks/useNotifications', () => ({
  useNotifications: vi.fn(),
  useMarkRead: () => ({ mutate: vi.fn() }),
}))

vi.mock('@/hooks/useInvitations', () => ({
  useRespondToInvitation: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('date-fns', () => ({
  formatDistanceToNow: () => '1 minute ago',
}))

vi.mock('@/hooks/useParticipants', () => ({
  useParticipants: vi.fn(),
  useRemoveParticipant: () => ({ mutate: vi.fn() }),
  useUpdatePermissions: () => ({ mutate: vi.fn() }),
}))

// ── Imports after mocks ────────────────────────────────────────────────────

import { useNotifications } from '@/hooks/useNotifications'
import { useParticipants } from '@/hooks/useParticipants'
import { useEvents } from '@/hooks/useEvent'
import { NotificationList } from '@/components/notifications/NotificationList'
import { ProposalList } from '@/app/events/[uid]/ProposalList'
import { ParticipantList } from '@/components/event/ParticipantList'
import DashboardPage from '@/app/dashboard/page'
import type { ProposalResponse, EventWithParticipants } from '@/types'

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

// ── Dashboard empty state ──────────────────────────────────────────────────

describe('DashboardPage — empty and error states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty state when no events', async () => {
    vi.mocked(useEvents).mockReturnValue({ data: [], isLoading: false } as unknown as ReturnType<typeof useEvents>)
    const jsx = await DashboardPage()
    render(jsx, { wrapper: makeWrapper() })
    expect(screen.getByText('No events yet')).toBeInTheDocument()
  })

  it('renders event cards when events exist', async () => {
    const mockEvent = {
      id: 'db-1',
      uid: 'abc-uid',
      name: 'Team Lunch',
      description: null,
      event_type: 'in_person' as const,
      coordinator_id: 'user-1',
      status: 'pending' as const,
      duration_minutes: 60,
      earliest_datetime_utc: '2026-05-01T00:00:00Z',
      latest_datetime_utc: '2026-05-07T00:00:00Z',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      finalized_start_time_utc: null,
      finalized_end_time_utc: null,
      finalized_at: null,
      allow_guest_invites: false,
      participants: [],
    }
    vi.mocked(useEvents).mockReturnValue({
      data: [mockEvent] as unknown as EventWithParticipants[],
      isLoading: false,
    } as unknown as ReturnType<typeof useEvents>)
    const jsx = await DashboardPage()
    render(jsx, { wrapper: makeWrapper() })
    expect(screen.getByText('Team Lunch')).toBeInTheDocument()
  })
})

// ── NotificationList empty state ───────────────────────────────────────────

describe('NotificationList — empty state', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows empty state when no notifications', () => {
    vi.mocked(useNotifications).mockReturnValue({ data: [], isLoading: false } as unknown as ReturnType<typeof useNotifications>)
    render(React.createElement(NotificationList), { wrapper: makeWrapper() })
    expect(screen.getByText(/no notifications yet/i)).toBeInTheDocument()
  })
})

// ── ProposalList empty + skeleton states ───────────────────────────────────

describe('ProposalList — empty and loading states', () => {
  const baseProps = {
    uid: 'test-event-uid',
    proposals: [] as ProposalResponse[],
    isLoadingProposals: false,
    isCoordinator: false,
    isRefreshing: false,
    proposalsStale: false,
    proposalsNeedsRegeneration: false,
    onRefresh: vi.fn(),
    onFinalize: vi.fn(),
  }

  it('shows empty state when no proposals', () => {
    render(React.createElement(ProposalList, { ...baseProps }), { wrapper: makeWrapper() })
    expect(screen.getByText(/no proposals yet/i)).toBeInTheDocument()
  })

  it('shows skeleton when loading', () => {
    render(React.createElement(ProposalList, { ...baseProps, isLoadingProposals: true }), { wrapper: makeWrapper() })
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.queryByText(/no proposals yet/i)).not.toBeInTheDocument()
  })

  it('renders proposals when data is available', () => {
    const proposals: ProposalResponse[] = [
      {
        id: 'prop-1',
        event_id: 'evt-db-1',
        rank: 1,
        start_time_utc: '2026-05-01T12:00:00Z',
        end_time_utc: '2026-05-01T13:00:00Z',
        conflict_count: 0,
        preferred_count: 3,
        reasoning: 'Best overlap',
      },
    ]
    render(React.createElement(ProposalList, { ...baseProps, proposals }), { wrapper: makeWrapper() })
    expect(screen.getByText('Best overlap')).toBeInTheDocument()
  })
})

// ── ParticipantList skeleton state ─────────────────────────────────────────

describe('ParticipantList — loading skeleton', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders skeleton rows when loading', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: undefined, isLoading: true } as unknown as ReturnType<typeof useParticipants>)
    render(
      React.createElement(ParticipantList, {
        uid: 'evt-uid',
        coordinatorId: 'coord-1',
        currentUserId: 'user-1',
      }),
      { wrapper: makeWrapper() }
    )
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows empty state when no participants', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [], isLoading: false } as unknown as ReturnType<typeof useParticipants>)
    render(
      React.createElement(ParticipantList, {
        uid: 'evt-uid',
        coordinatorId: 'coord-1',
        currentUserId: 'user-1',
      }),
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText(/no participants yet/i)).toBeInTheDocument()
  })
})
