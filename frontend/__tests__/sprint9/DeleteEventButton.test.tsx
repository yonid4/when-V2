/**
 * Sprint 9B — DeleteModal component
 *
 * Covers:
 * - Renders the modal with event name
 * - Cancel button calls onClose
 * - Confirm button calls deleteEvent with correct uid
 * - Redirects to /dashboard after successful delete
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const mockPush = vi.fn()
const mockRefresh = vi.fn()
const mockDeleteEvent = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), refresh: mockRefresh }),
}))

vi.mock('@/hooks/useEvent', () => ({
  useDeleteEvent: () => ({ mutate: mockDeleteEvent, isPending: false }),
}))

import { DeleteModal } from '@/components/event/DeleteModal'
import type { EventWithParticipants } from '@/types'

const mockEvent: EventWithParticipants = {
  id: 'db-id-1',
  uid: 'abc-uid-1',
  name: 'Team Lunch',
  description: null,
  event_type: 'in_person',
  coordinator_id: 'coord-1',
  status: 'pending',
  duration_minutes: 60,
  earliest_date: '2026-05-01',
  latest_date: '2026-05-07',
  start_time: '12:00',
  end_time: '13:00',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  finalized_start_time_utc: null,
  finalized_end_time_utc: null,
  finalized_at: null,
  allow_guest_invites: false,
  participants: [],
}

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('DeleteModal', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders with event name', () => {
    render(
      React.createElement(DeleteModal, { event: mockEvent, onClose }),
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText(/"Team Lunch"/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete event/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('calls onClose when cancel is clicked', () => {
    render(
      React.createElement(DeleteModal, { event: mockEvent, onClose }),
      { wrapper: makeWrapper() }
    )
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalledOnce()
    expect(mockDeleteEvent).not.toHaveBeenCalled()
  })

  it('calls deleteEvent with event uid on confirm', () => {
    render(
      React.createElement(DeleteModal, { event: mockEvent, onClose }),
      { wrapper: makeWrapper() }
    )
    fireEvent.click(screen.getByRole('button', { name: /delete event/i }))
    expect(mockDeleteEvent).toHaveBeenCalledWith(
      'abc-uid-1',
      expect.objectContaining({ onSuccess: expect.any(Function) })
    )
  })

  it('redirects to /dashboard after successful delete', () => {
    render(
      React.createElement(DeleteModal, { event: mockEvent, onClose }),
      { wrapper: makeWrapper() }
    )
    fireEvent.click(screen.getByRole('button', { name: /delete event/i }))
    // Simulate onSuccess callback
    const onSuccess = vi.mocked(mockDeleteEvent).mock.calls[0][1].onSuccess
    onSuccess()
    expect(mockRefresh).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })
})
