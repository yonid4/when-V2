import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ParticipantList } from '@/components/event/ParticipantList'
import type { Participant } from '@/types'

// Mock hooks
const mockRemove = vi.fn()
const mockUpdatePermissions = vi.fn()

vi.mock('@/hooks/useParticipants', () => ({
  useParticipants: vi.fn(),
  useRemoveParticipant: () => ({ mutate: mockRemove }),
  useUpdatePermissions: () => ({ mutate: mockUpdatePermissions }),
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

describe('ParticipantList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: undefined, isLoading: true } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows empty state when no participants', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [], isLoading: false } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(screen.getByText(/no participants yet/i)).toBeInTheDocument()
  })

  it('renders participant name', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ full_name: 'Alice' })],
      isLoading: false,
    } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(screen.getByText('Alice')).toBeInTheDocument()
  })

  it('shows COORDINATOR label for the coordinator', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ user_id: 'coord-1', full_name: 'Boss' })],
      isLoading: false,
    } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(screen.getByText('Coordinator')).toBeInTheDocument()
  })

  it('shows remove button for coordinator targeting non-coordinator participant', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [
        makeParticipant({ user_id: 'coord-1', full_name: 'Boss' }),
        makeParticipant({ user_id: 'user-2', full_name: 'Bob' }),
      ],
      isLoading: false,
    } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />)
    // Remove button for non-coordinator participant
    const removeButtons = screen.getAllByTitle('Remove participant')
    expect(removeButtons.length).toBeGreaterThan(0)
  })

  it('calls removeParticipant when leave button clicked by self', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [makeParticipant({ user_id: 'user-1', full_name: 'Alice' })],
      isLoading: false,
    } as any)
    render(<ParticipantList uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    const leaveBtn = screen.getByTitle('Leave event')
    fireEvent.click(leaveBtn)
    expect(mockRemove).toHaveBeenCalledWith('user-1')
  })
})
