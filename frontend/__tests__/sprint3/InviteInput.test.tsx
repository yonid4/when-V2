import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { InviteInput } from '@/components/event/InviteInput'

const mockInvite = vi.fn()

vi.mock('@/hooks/useInvitations', () => ({
  useInvite: () => ({ mutate: mockInvite, isPending: false }),
}))

vi.mock('@/hooks/useParticipants', () => ({
  useParticipants: vi.fn(),
}))

import { useParticipants } from '@/hooks/useParticipants'

describe('InviteInput', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders invite form for coordinator', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    render(<InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />)
    expect(screen.getByPlaceholderText(/invite by email/i)).toBeInTheDocument()
    expect(screen.getByText('Invite')).toBeInTheDocument()
  })

  it('returns null when user has no invite permission', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [{ user_id: 'user-1', can_invite: false }],
    } as any)
    const { container } = render(
      <InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows error for invalid email', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    render(<InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />)
    fireEvent.change(screen.getByPlaceholderText(/invite by email/i), {
      target: { value: 'not-an-email' },
    })
    fireEvent.click(screen.getByText('Invite'))
    expect(screen.getByText(/valid email/i)).toBeInTheDocument()
  })

  it('shows error when email field is empty', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    render(<InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />)
    fireEvent.click(screen.getByText('Invite'))
    expect(screen.getByText(/please enter an email/i)).toBeInTheDocument()
  })

  it('calls invite with email on valid submit', () => {
    vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
    render(<InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="coord-1" />)
    fireEvent.change(screen.getByPlaceholderText(/invite by email/i), {
      target: { value: 'bob@example.com' },
    })
    fireEvent.click(screen.getByText('Invite'))
    expect(mockInvite).toHaveBeenCalledWith('bob@example.com', expect.any(Object))
  })

  it('renders form for participant with can_invite=true', () => {
    vi.mocked(useParticipants).mockReturnValue({
      data: [{ user_id: 'user-1', can_invite: true }],
    } as any)
    render(<InviteInput uid="uid-1" coordinatorId="coord-1" currentUserId="user-1" />)
    expect(screen.getByPlaceholderText(/invite by email/i)).toBeInTheDocument()
  })
})
