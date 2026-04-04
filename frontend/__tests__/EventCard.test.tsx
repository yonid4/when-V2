import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import EventCard from '@/components/dashboard/EventCard'
import type { EventWithParticipants } from '@/types'

// Mock next/link — renders a plain <a>
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

function makeEvent(overrides: Partial<EventWithParticipants> = {}): EventWithParticipants {
  return {
    id: 'evt-1',
    uid: 'abc123def456',
    name: 'Team Standup',
    description: null,
    event_type: 'meeting',
    coordinator_id: 'u1',
    earliest_datetime_utc: '2026-04-10T09:00:00Z',
    latest_datetime_utc: '2026-04-10T17:00:00Z',
    duration_minutes: 30,
    status: 'planning',
    location: null,
    video_call_link: null,
    finalized_start_time_utc: null,
    finalized_end_time_utc: null,
    google_calendar_event_id: null,
    proposals_needs_regeneration: false,
    proposals_last_generated_at: null,
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    finalized_at: null,
    participants: [],
    ...overrides,
  }
}

describe('EventCard', () => {
  it('renders event name', () => {
    render(<EventCard event={makeEvent()} />)
    expect(screen.getByText('Team Standup')).toBeInTheDocument()
  })

  it('renders event type badge', () => {
    render(<EventCard event={makeEvent({ event_type: 'social' })} />)
    expect(screen.getByText('social')).toBeInTheDocument()
  })

  it('renders status badge with correct text', () => {
    render(<EventCard event={makeEvent({ status: 'confirmed' })} />)
    expect(screen.getByText('confirmed')).toBeInTheDocument()
  })

  it('links to event detail page using uid', () => {
    render(<EventCard event={makeEvent({ uid: 'myuid123' })} />)
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/events/myuid123')
  })

  it('shows participant avatars with initials when no avatar_url', () => {
    const event = makeEvent({
      participants: [
        {
          event_id: 'evt-1',
          user_id: 'u1',
          status: 'accepted',
          rsvp_status: 'going',
          can_invite: true,
          joined_at: '2026-04-01T00:00:00Z',
          full_name: 'Alice',
          avatar_url: null,
          email_address: 'alice@example.com',
        },
      ],
    })
    render(<EventCard event={event} />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('shows overflow count when more than 4 participants', () => {
    const participants = Array.from({ length: 6 }, (_, i) => ({
      event_id: 'evt-1',
      user_id: `u${i}`,
      status: 'accepted' as const,
      rsvp_status: 'going' as const,
      can_invite: false,
      joined_at: '2026-04-01T00:00:00Z',
      full_name: `User ${i}`,
      avatar_url: null,
      email_address: `user${i}@example.com`,
    }))
    render(<EventCard event={makeEvent({ participants })} />)
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('has hover lift class on card', () => {
    const { container } = render(<EventCard event={makeEvent()} />)
    const card = container.querySelector('.group-hover\\:-translate-y-1')
    expect(card).toBeInTheDocument()
  })
})
