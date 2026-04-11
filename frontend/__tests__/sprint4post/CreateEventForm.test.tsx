/**
 * Sprint 4 (Post) — NewEventPage / Step 2 tests
 *
 * Covers:
 * - Step 2 default values (start_time=09:00, end_time=17:00, duration=60)
 * - End-before-start blocking (end_time <= start_time on same day)
 * - Same-day time blocking
 * - api.post called once per participant email after event creation
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──
// Use vi.hoisted so these variables are available inside factory functions

const { mockPush, mockCreateEvent, mockApiPost, mockInviteParticipant } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockCreateEvent: vi.fn(),
  mockApiPost: vi.fn().mockResolvedValue({}),
  mockInviteParticipant: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { channel: vi.fn(() => ({ on: vi.fn(), subscribe: vi.fn(), unsubscribe: vi.fn() })) },
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/hooks/useEvent', () => ({
  useCreateEvent: () => ({ mutate: mockCreateEvent, isPending: false }),
}))

vi.mock('@/lib/api', () => ({
  api: { post: mockApiPost },
}))

vi.mock('@/hooks/useInvitations', () => ({
  useInviteParticipant: () => ({ mutateAsync: mockInviteParticipant, isPending: false }),
  useRespondToInvitation: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: any) => <a href={href} {...props}>{children}</a>,
}))

import NewEventPage, { validateStep2Times } from '@/app/events/new/page'

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Pure function tests ─────────────────────────────────────────────────────

describe('validateStep2Times — pure function', () => {
  it('returns null when end date is after start date', () => {
    const result = validateStep2Times({
      earliest_date: '2025-01-01',
      latest_date: '2025-01-08',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).toBeNull()
  })

  it('returns latest_date error when end date is before start date', () => {
    const result = validateStep2Times({
      earliest_date: '2025-01-10',
      latest_date: '2025-01-05',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).toEqual({
      field: 'latest_date',
      message: 'End date must be on or after start date',
    })
  })

  it('returns end_time error when same day and end_time <= start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2025-01-01',
      latest_date: '2025-01-01',
      start_time: '17:00',
      end_time: '09:00',
    })
    expect(result).toEqual({
      field: 'end_time',
      message: 'End time must be after start time on the same day',
    })
  })

  it('returns end_time error when same day and end_time equals start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2025-01-01',
      latest_date: '2025-01-01',
      start_time: '10:00',
      end_time: '10:00',
    })
    expect(result).toEqual({
      field: 'end_time',
      message: 'End time must be after start time on the same day',
    })
  })

  it('returns null when same day and end_time is after start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2025-01-01',
      latest_date: '2025-01-01',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).toBeNull()
  })
})

// ─── Step 2 default values ───────────────────────────────────────────────────

describe('NewEventPage — Step 2 defaults', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function advanceToStep2() {
    renderWithQuery(<NewEventPage />)
    // Fill in Step 1 and click Next
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., sunday brunch/i), {
      target: { value: 'Test Event' },
    })
    fireEvent.click(screen.getByText('Next: Availability'))
    await waitFor(() => screen.getByText('Find the perfect window'))
  }

  it('renders earliest_date input with today as default', async () => {
    await advanceToStep2()
    const today = new Date().toISOString().split('T')[0]
    expect(screen.getByDisplayValue(today)).toBeInTheDocument()
  })

  it('renders latest_date input with 7 days from today as default', async () => {
    await advanceToStep2()
    const sevenDays = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    expect(screen.getByDisplayValue(sevenDays)).toBeInTheDocument()
  })

  it('renders start_time input with default 09:00', async () => {
    await advanceToStep2()
    const startInput = screen.getByDisplayValue('09:00')
    expect(startInput).toBeInTheDocument()
  })

  it('renders end_time input with default 17:00', async () => {
    await advanceToStep2()
    const endInput = screen.getByDisplayValue('17:00')
    expect(endInput).toBeInTheDocument()
  })

  it('renders 1 hr duration as default selected', async () => {
    await advanceToStep2()
    // 1 hr button should have the highlighted class
    const oneHrBtn = screen.getByText('1 hr')
    expect(oneHrBtn.className).toContain('bg-primary-container')
  })
})

// ─── Step 2 submission blocking ─────────────────────────────────────────────

describe('NewEventPage — Step 2 blocks submission on invalid dates/times', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function advanceToStep2() {
    renderWithQuery(<NewEventPage />)
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., sunday brunch/i), {
      target: { value: 'Block Test' },
    })
    fireEvent.click(screen.getByText('Next: Availability'))
    await waitFor(() => screen.getByText('Find the perfect window'))
  }

  it('does not advance to step 3 when end date is before start date', async () => {
    await advanceToStep2()

    const dateInputs = screen.getAllByDisplayValue(/^\d{4}-\d{2}-\d{2}$/)
    fireEvent.change(dateInputs[0], { target: { value: '2026-05-10' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-05-05' } })

    fireEvent.click(screen.getByText('Next: Confirmation'))

    // Step 3 heading must NOT appear
    expect(screen.queryByText('Almost there.')).toBeNull()
    // Still on step 2
    expect(screen.getByText('Find the perfect window')).toBeInTheDocument()
  })

  it('does not advance to step 3 when same-day end time is before start time', async () => {
    await advanceToStep2()

    const dateInputs = screen.getAllByDisplayValue(/^\d{4}-\d{2}-\d{2}$/)
    fireEvent.change(dateInputs[0], { target: { value: '2026-05-10' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-05-10' } })

    const timeInputs = screen.getAllByDisplayValue(/^\d{2}:\d{2}$/)
    fireEvent.change(timeInputs[0], { target: { value: '17:00' } })
    fireEvent.change(timeInputs[1], { target: { value: '09:00' } })

    fireEvent.click(screen.getByText('Next: Confirmation'))

    expect(screen.queryByText('Almost there.')).toBeNull()
    expect(screen.getByText('Find the perfect window')).toBeInTheDocument()
  })
})

// ─── api.post per participant ────────────────────────────────────────────────

describe('NewEventPage — api.post called per participant', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls api.post once per participant email after event creation', async () => {
    renderWithQuery(<NewEventPage />)

    // Step 1
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., sunday brunch/i), {
      target: { value: 'Test Event' },
    })
    fireEvent.click(screen.getByText('Next: Availability'))
    await waitFor(() => screen.getByText('Find the perfect window'))

    // Add two participant emails
    const emailInput = screen.getByPlaceholderText(/add by email/i)
    fireEvent.change(emailInput, { target: { value: 'alice@example.com' } })
    fireEvent.click(screen.getByText('Add'))

    fireEvent.change(emailInput, { target: { value: 'bob@example.com' } })
    fireEvent.click(screen.getByText('Add'))

    // Go to step 3
    fireEvent.click(screen.getByText('Next: Confirmation'))
    await waitFor(() => screen.getByText('Almost there.'))

    // Submit
    fireEvent.click(screen.getByText('Create Event'))

    // createEvent called with correct shape
    expect(mockCreateEvent).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Test Event' }),
      expect.objectContaining({ onSuccess: expect.any(Function) })
    )

    // Simulate onSuccess with a fake event
    const [, { onSuccess }] = mockCreateEvent.mock.calls[0]
    await onSuccess({ uid: 'evt-uid-123' })

    expect(mockInviteParticipant).toHaveBeenCalledTimes(2)
    expect(mockInviteParticipant).toHaveBeenCalledWith({ uid: 'evt-uid-123', email: 'alice@example.com' })
    expect(mockInviteParticipant).toHaveBeenCalledWith({ uid: 'evt-uid-123', email: 'bob@example.com' })
    expect(mockPush).toHaveBeenCalledWith('/events/evt-uid-123')
  })
})
