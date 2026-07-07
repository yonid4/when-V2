/**
 * Security (H1) — video_call_link stored-XSS guard.
 *
 * The confirmed-event banner in EventDetailClient renders `video_call_link`
 * into an anchor href. A `javascript:` URL there is a stored-XSS sink, so the
 * component must render the anchor ONLY for http(s) links and fall back to
 * plain text otherwise. Also covers the shared `isSafeHttpUrl` helper.
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('@/hooks/useEvent', () => ({
  useEvent: vi.fn(),
  useUpdateEvent: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteEvent: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/useBusySlots', () => ({
  useSyncCalendar: () => ({ mutate: vi.fn(), isPending: false }),
  useSyncMyCalendar: () => ({ mutate: vi.fn(), isPending: false }),
}))

// IMPORTANT: hooks that return arrays must return a STABLE reference.
// EventDetailClient syncs `preferredSlots` into state via a ref-compare
// effect; a fresh `[]` per call re-triggers that effect on every render,
// causing an infinite setState loop that OOMs the vitest worker.
vi.mock('@/hooks/usePreferredSlots', () => {
  const emptySlots: unknown[] = []
  return {
    usePreferredSlots: () => ({ data: emptySlots }),
    useSavePreferredSlot: () => ({ mutateAsync: vi.fn() }),
    useDeletePreferredSlot: () => ({ mutateAsync: vi.fn() }),
  }
})

vi.mock('@/hooks/useAvailabilitySegments', () => {
  const emptySegments: unknown[] = []
  return {
    useAvailabilitySegments: () => ({ data: emptySegments }),
  }
})

vi.mock('@/hooks/useProposals', () => {
  const emptyProposals: unknown[] = []
  return {
    useProposals: () => ({ data: emptyProposals, isLoading: false }),
    useRefreshProposals: () => ({ mutate: vi.fn(), isPending: false }),
  }
})

vi.mock('@/hooks/useProposalFreshness', () => ({
  useProposalFreshness: () => ({ isChecking: false, checkAndRefreshIfNeeded: vi.fn() }),
}))

vi.mock('@/hooks/useEventSubscriptions', () => {
  const emptyPresence: unknown[] = []
  return {
    useEventSubscriptions: () => {},
    useEventPresence: () => emptyPresence,
  }
})

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: vi.fn(), refetchQueries: vi.fn() }),
  }
})

vi.mock('@/lib/supabase', () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
      unsubscribe: vi.fn(),
    })),
    removeChannel: vi.fn(),
  },
}))

// ─── Stub child components so only EventDetailClient's own JSX renders ────────

vi.mock('@/components/layout/Navbar', () => ({ Navbar: () => <nav>Navbar</nav> }))
vi.mock('@/app/events/[uid]/GridHeader', () => ({ GridHeader: () => <div>GridHeader</div> }))
vi.mock('@/app/events/[uid]/FinalizeCard', () => ({ FinalizeCard: () => <div>FinalizeCard</div> }))
vi.mock('@/app/events/[uid]/ProposalList', () => ({ ProposalList: () => <div>ProposalList</div> }))
vi.mock('@/components/event/AvailabilityGrid', () => ({ AvailabilityGrid: () => <div>AvailabilityGrid</div> }))
vi.mock('@/components/event/ParticipantList', () => ({ ParticipantList: () => <div>Participant List</div> }))
vi.mock('@/components/event/InviteInput', () => ({ InviteInput: () => <div>Invite Input</div> }))
vi.mock('@/components/event/RsvpSelector', () => ({ RsvpSelector: () => <div>RSVP Selector</div> }))
vi.mock('@/components/event/EditModal', () => ({ EditModal: () => <div>EditModal</div> }))
vi.mock('@/components/event/DeleteModal', () => ({ DeleteModal: () => <div>DeleteModal</div> }))

import { useAuthStore } from '@/stores/authStore'
import { useEvent } from '@/hooks/useEvent'
import EventDetailClient from '@/app/events/[uid]/EventDetailClient'
import { isSafeHttpUrl } from '@/lib/eventUtils'
import type { EventWithParticipants } from '@/types'

function makeConfirmedEvent(videoCallLink: string): EventWithParticipants {
  return {
    id: 'event-db-id-1',
    uid: 'event-uid-1',
    name: 'Team Sync',
    description: null,
    event_type: 'meeting',
    coordinator_id: 'user-coordinator',
    earliest_datetime_utc: '2026-04-10T09:00:00.000Z',
    latest_datetime_utc: '2026-04-17T17:00:00.000Z',
    duration_minutes: 60,
    status: 'confirmed',
    location: null,
    video_call_link: videoCallLink,
    finalized_start_time_utc: '2026-04-12T14:00:00.000Z',
    finalized_end_time_utc: '2026-04-12T15:00:00.000Z',
    allow_guest_invites: false,
    calendar_event_id: null,
    proposals_needs_regeneration: false,
    proposals_last_generated_at: null,
    created_at: '2026-04-01T00:00:00.000Z',
    updated_at: '2026-04-01T00:00:00.000Z',
    finalized_at: '2026-04-11T00:00:00.000Z',
    participants: [],
  }
}

describe('isSafeHttpUrl', () => {
  it('accepts http and https URLs', () => {
    expect(isSafeHttpUrl('https://meet.example.com/x')).toBe(true)
    expect(isSafeHttpUrl('http://meet.example.com/x')).toBe(true)
  })

  it('rejects javascript: URLs, including whitespace/control-char disguises', () => {
    expect(isSafeHttpUrl('javascript:alert(1)')).toBe(false)
    expect(isSafeHttpUrl('\tjavascript:alert(1)')).toBe(false)
    expect(isSafeHttpUrl(' javascript:alert(1)')).toBe(false)
    expect(isSafeHttpUrl('java\nscript:alert(1)')).toBe(false)
  })

  it('rejects other non-http schemes and non-URLs', () => {
    expect(isSafeHttpUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
    expect(isSafeHttpUrl('not a url')).toBe(false)
    expect(isSafeHttpUrl('')).toBe(false)
    expect(isSafeHttpUrl(null)).toBe(false)
    expect(isSafeHttpUrl(undefined)).toBe(false)
  })
})

describe('EventDetailClient — video_call_link rendering (H1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: 'user-coordinator', email_address: 'coord@example.com' },
    } as never)
  })

  it('renders a javascript: link as plain text, never as an anchor', () => {
    vi.mocked(useEvent).mockReturnValue({
      data: makeConfirmedEvent('javascript:alert(1)'),
      isLoading: false,
      error: null,
    } as never)

    render(<EventDetailClient uid="event-uid-1" />)

    // No anchor may point at the javascript: payload.
    const anchors = screen.queryAllByRole('link')
    expect(
      anchors.some((a) => (a.getAttribute('href') ?? '').toLowerCase().includes('javascript'))
    ).toBe(false)

    // The raw value is shown as inert plain text instead.
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument()
  })

  it('renders an https link as a clickable anchor', () => {
    vi.mocked(useEvent).mockReturnValue({
      data: makeConfirmedEvent('https://meet.example.com/x'),
      isLoading: false,
      error: null,
    } as never)

    render(<EventDetailClient uid="event-uid-1" />)

    const link = screen.getByRole('link', { name: /join video call/i })
    expect(link).toHaveAttribute('href', 'https://meet.example.com/x')
  })
})
