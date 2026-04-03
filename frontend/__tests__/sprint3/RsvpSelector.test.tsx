import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RsvpSelector } from '@/components/event/RsvpSelector'
import type { Participant } from '@/types'

const mockUpdateRsvp = vi.fn()

vi.mock('@/hooks/useParticipants', () => ({
  useParticipants: vi.fn(),
  useUpdateRsvp: () => ({ mutate: mockUpdateRsvp, isPending: false }),
}))

import { useParticipants } from '@/hooks/useParticipants'

function makeParticipant(overrides: Partial<Participant> = {}): Participant {
  return {
    event_id: 'evt-1',
    user_id: 'user-1',
    status: 'accepted',
    rsvp_status: 'going',
    can_invite: false,
    joined_at: '2026-04-01T00:00:00Z',
    full_name: 'Alice',
    avatar_url: null,
    email_address: 'alice@example.com',
    ...overrides,
  }
}

describe('RsvpSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns null for the coordinator', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    const { container } = render(
      <RsvpSelector uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />
    )
    expect(container.firstChild).toBeNull()
  })

  it('returns null when user is not a participant', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    const { container } = render(
      <RsvpSelector uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders three RSVP buttons for a non-coordinator participant', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ user_id: 'user-1', rsvp_status: 'going' })],
    } as any)
    render(<RsvpSelector uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(screen.getByText('Going')).toBeInTheDocument()
    expect(screen.getByText('Maybe')).toBeInTheDocument()
    expect(screen.getByText('Not Going')).toBeInTheDocument()
  })

  it('calls updateRsvp when an option is clicked', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ user_id: 'user-1', rsvp_status: 'going' })],
    } as any)
    render(<RsvpSelector uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    fireEvent.click(screen.getByText('Maybe'))
    expect(mockUpdateRsvp).toHaveBeenCalledWith({
      userId: 'user-1',
      rsvp_status: 'maybe',
    })
  })

  it('shows active style for current rsvp_status', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ user_id: 'user-1', rsvp_status: 'maybe' })],
    } as any)
    render(<RsvpSelector uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    const maybeBtn = screen.getByText('Maybe')
    expect(maybeBtn.className).toContain('bg-primary')
  })
})
