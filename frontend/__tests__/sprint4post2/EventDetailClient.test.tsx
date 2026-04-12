/**
 * Sprint 4 (Post-2) — EventDetailClient component tests
 *
 * Covers:
 * - Renders event name and status badge
 * - Edit modal shows all editable fields (name, allow_guest_invites, earliest_local,
 *   latest_local, event_type, duration_minutes)
 * - Copy Link copies window.location.href and changes button label
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('@/hooks/useEvent', () => ({
  useUpdateEvent: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteEvent: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/useBusySlots', () => ({
  useSyncCalendar: () => ({ mutate: vi.fn(), isPending: false }),
  useSyncMyCalendar: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/usePreferredSlots', () => ({
  usePreferredSlots: () => ({ data: [] }),
  useSavePreferredSlot: () => ({ mutateAsync: vi.fn() }),
  useDeletePreferredSlot: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return { ...actual, useQueryClient: () => ({ invalidateQueries: vi.fn() }) }
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

vi.mock('@/components/event/ParticipantList', () => ({
  ParticipantList: () => <div>Participant List</div>,
}))

vi.mock('@/components/event/InviteInput', () => ({
  InviteInput: () => <div>Invite Input</div>,
}))

vi.mock('@/components/event/RsvpSelector', () => ({
  RsvpSelector: () => <div>RSVP Selector</div>,
}))

vi.mock('@/components/layout/Navbar', () => ({
  Navbar: () => <nav>Navbar</nav>,
}))

vi.mock('@/lib/gridUtils', () => ({
  getSlotsForCell: () => [],
}))

import { useAuthStore } from '@/stores/authStore'
import EventDetailClient from '@/app/events/[uid]/EventDetailClient'
import type { EventWithParticipants } from '@/types'

function makeEvent(overrides: Partial<EventWithParticipants> = {}): EventWithParticipants {
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
    status: 'planning',
    location: null,
    video_call_link: null,
    finalized_start_time_utc: null,
    finalized_end_time_utc: null,
    allow_guest_invites: false,
    google_calendar_event_id: null,
    proposals_needs_regeneration: false,
    proposals_last_generated_at: null,
    created_at: '2026-04-01T00:00:00.000Z',
    updated_at: '2026-04-01T00:00:00.000Z',
    finalized_at: null,
    participants: [],
    ...overrides,
  }
}

describe.skip('EventDetailClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuthStore).mockReturnValue({
      user: { id: 'user-coordinator', email_address: 'coord@example.com' },
    } as any)
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('renders event name', () => {
    render(<EventDetailClient event={makeEvent()} />)
    expect(screen.getByText('Team Sync')).toBeInTheDocument()
  })

  it('renders status badge with planning status', () => {
    render(<EventDetailClient event={makeEvent({ status: 'planning' })} />)
    expect(screen.getByText(/planning/i)).toBeInTheDocument()
  })

  it('opens edit modal when Edit button is clicked', async () => {
    render(<EventDetailClient event={makeEvent()} />)

    const editBtn = screen.getByLabelText('Edit event')
    fireEvent.click(editBtn)

    await waitFor(() => screen.getByText('Edit Event'))
  })

  it('edit modal shows event name input field', async () => {
    render(<EventDetailClient event={makeEvent()} />)
    fireEvent.click(screen.getByLabelText('Edit event'))

    await waitFor(() => {
      const nameInput = screen.getByDisplayValue('Team Sync')
      expect(nameInput).toBeInTheDocument()
    })
  })

  it('edit modal shows allow_guest_invites checkbox', async () => {
    render(<EventDetailClient event={makeEvent()} />)
    fireEvent.click(screen.getByLabelText('Edit event'))

    await waitFor(() => {
      expect(screen.getByText(/allow guests to invite others/i)).toBeInTheDocument()
    })
  })

  it('edit modal shows earliest_local datetime-local input', async () => {
    render(<EventDetailClient event={makeEvent()} />)
    fireEvent.click(screen.getByLabelText('Edit event'))

    await waitFor(() => {
      expect(screen.getByText(/earliest time/i)).toBeInTheDocument()
    })
  })

  it('edit modal shows event_type select', async () => {
    render(<EventDetailClient event={makeEvent({ event_type: 'meeting' })} />)
    fireEvent.click(screen.getByLabelText('Edit event'))

    await waitFor(() => {
      const select = screen.getByDisplayValue('Meeting')
      expect(select).toBeInTheDocument()
    })
  })

  it('edit modal shows duration_minutes number input', async () => {
    render(<EventDetailClient event={makeEvent({ duration_minutes: 60 })} />)
    fireEvent.click(screen.getByLabelText('Edit event'))

    await waitFor(() => {
      expect(screen.getByDisplayValue('60')).toBeInTheDocument()
    })
  })

  it('Copy Link button copies window.location.href and label changes to Copied!', async () => {
    render(<EventDetailClient event={makeEvent()} />)

    const copyBtn = screen.getByText('Copy Link')
    fireEvent.click(copyBtn)

    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument()
    })
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(window.location.href)
  })
})
