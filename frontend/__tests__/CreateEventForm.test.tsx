import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock next/navigation
const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

// Mock useCreateEvent
const mockCreateEvent = vi.fn()
vi.mock('@/hooks/useEvent', () => ({
  useCreateEvent: () => ({
    mutate: mockCreateEvent,
    isPending: false,
  }),
}))

import NewEventPage from '@/app/events/new/page'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('CreateEventForm (NewEventPage)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders step 1 with event name input and type cards', () => {
    renderWithProviders(<NewEventPage />)
    expect(screen.getByText('Create a New Event')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Sunday Brunch/i)).toBeInTheDocument()
    expect(screen.getByText('Meeting')).toBeInTheDocument()
    expect(screen.getByText('Social')).toBeInTheDocument()
    expect(screen.getByText('Birthday')).toBeInTheDocument()
    expect(screen.getByText('Other')).toBeInTheDocument()
  })

  it('shows step indicator with "Details" active on step 1', () => {
    renderWithProviders(<NewEventPage />)
    expect(screen.getByText('Details')).toBeInTheDocument()
    expect(screen.getByText('Availability')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
  })

  it('shows validation error when submitting step 1 without event name', async () => {
    renderWithProviders(<NewEventPage />)
    const nextButton = screen.getByRole('button', { name: /Next: Availability/i })
    fireEvent.click(nextButton)
    await waitFor(() => {
      expect(screen.getByText('Event name is required')).toBeInTheDocument()
    })
  })

  it('advances to step 2 after filling step 1', async () => {
    renderWithProviders(<NewEventPage />)

    // Fill event name
    const nameInput = screen.getByPlaceholderText(/Sunday Brunch/i)
    fireEvent.change(nameInput, { target: { value: 'Test Event' } })

    // Submit step 1
    const nextButton = screen.getByRole('button', { name: /Next: Availability/i })
    fireEvent.click(nextButton)

    await waitFor(() => {
      expect(screen.getByText('Find the perfect window')).toBeInTheDocument()
    })
  })

  it('renders duration segmented selector on step 2', async () => {
    renderWithProviders(<NewEventPage />)

    // Fill step 1 and advance
    fireEvent.change(screen.getByPlaceholderText(/Sunday Brunch/i), { target: { value: 'Test' } })
    fireEvent.click(screen.getByRole('button', { name: /Next: Availability/i }))

    await waitFor(() => {
      expect(screen.getByText('30 min')).toBeInTheDocument()
      expect(screen.getByText('1 hr')).toBeInTheDocument()
      expect(screen.getByText('1.5 hr')).toBeInTheDocument()
      expect(screen.getByText('2 hr')).toBeInTheDocument()
    })
  })

  it('shows "Back to Dashboard" link on step 1', () => {
    renderWithProviders(<NewEventPage />)
    const backLink = screen.getByText('Back to Dashboard')
    expect(backLink.closest('a')).toHaveAttribute('href', '/dashboard')
  })
})
