/**
 * Sprint 4 (Post-2) — NewEventPage integration tests
 *
 * Covers:
 * - validateStep2Times error strings
 * - start_time / end_time included in API payload as datetime UTC ISO strings
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──
// Use vi.hoisted so these variables are available inside factory functions

const { mockPush, mockCreateEvent, mockApiPost } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockCreateEvent: vi.fn(),
  mockApiPost: vi.fn().mockResolvedValue({}),
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

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: any) => <a href={href} {...props}>{children}</a>,
}))

import NewEventPage, { validateStep2Times } from '@/app/events/new/page'

// ─── validateStep2Times error strings ────────────────────────────────────────

describe('validateStep2Times — error message strings', () => {
  it('returns error with field latest_date and descriptive message for inverted dates', () => {
    const result = validateStep2Times({
      earliest_date: '2026-05-10',
      latest_date: '2026-05-05',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).not.toBeNull()
    expect(result!.field).toBe('latest_date')
    expect(result!.message).toMatch(/on or after start date/i)
  })

  it('returns error with field end_time and descriptive message when same day and time inverted', () => {
    const result = validateStep2Times({
      earliest_date: '2026-05-10',
      latest_date: '2026-05-10',
      start_time: '14:00',
      end_time: '09:00',
    })
    expect(result).not.toBeNull()
    expect(result!.field).toBe('end_time')
    expect(result!.message).toMatch(/after start time/i)
  })

  it('returns null for valid date range spanning multiple days', () => {
    const result = validateStep2Times({
      earliest_date: '2026-05-01',
      latest_date: '2026-05-08',
      start_time: '17:00',
      end_time: '09:00',
    })
    expect(result).toBeNull()
  })
})

// ─── start_time / end_time in API payload ─────────────────────────────────────

describe('NewEventPage — start_time/end_time in event creation payload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends earliest_datetime_utc and latest_datetime_utc as ISO strings', async () => {
    render(<NewEventPage />)

    // Step 1
    fireEvent.change(screen.getByPlaceholderText(/e\.g\., sunday brunch/i), {
      target: { value: 'Payload Test' },
    })
    fireEvent.click(screen.getByText('Next: Availability'))
    await waitFor(() => screen.getByText('Find the perfect window'))

    // Step 2 — use the default start/end dates that are pre-filled; clear and set specific values
    const dateInputs = screen.getAllByDisplayValue(/^\d{4}-\d{2}-\d{2}$/)
    // earliest_date is dateInputs[0], latest_date is dateInputs[1]
    fireEvent.change(dateInputs[0], { target: { value: '2026-06-01' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-06-08' } })

    // Set start_time and end_time
    const timeInputs = screen.getAllByDisplayValue(/^\d{2}:\d{2}$/)
    fireEvent.change(timeInputs[0], { target: { value: '10:00' } })
    fireEvent.change(timeInputs[1], { target: { value: '18:00' } })

    fireEvent.click(screen.getByText('Next: Confirmation'))
    await waitFor(() => screen.getByText('Almost there.'))

    fireEvent.click(screen.getByText('Create Event'))

    expect(mockCreateEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        earliest_datetime_utc: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
        latest_datetime_utc: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      }),
      expect.any(Object)
    )
  })
})
