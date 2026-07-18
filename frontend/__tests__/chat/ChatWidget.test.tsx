/**
 * Package 7 (chat UI) — ChatWidget tests
 *
 * Covers:
 * - FAB renders on an authenticated private page; hidden once the drawer opens
 * - Clicking the FAB opens the drawer
 * - Sending a message posts { message, context } — the event route carries event_uid
 * - Clicking an assistant action button posts the exact structured action (no free text)
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Mutable holders shared with the hoisted vi.mock factories ────────────────
const mocks = vi.hoisted(() => ({
  sendTurn: vi.fn(),
  createThread: vi.fn(),
  pathname: '/dashboard',
  threads: [] as Array<{
    id: string
    title: string | null
    status: string
    created_at: string
    updated_at: string
  }>,
  messages: [] as Array<{
    id: string
    thread_id: string
    role: 'user' | 'assistant'
    content: string
    payload?: unknown
    created_at: string
  }>,
}))

vi.mock('next/navigation', () => ({
  usePathname: () => mocks.pathname,
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: unknown }) => unknown) =>
    selector({ user: { id: 'u1', email_address: 'me@example.com' } }),
}))

vi.mock('@/hooks/useChat', () => ({
  useChatThreads: () => ({ data: mocks.threads, isLoading: false }),
  useChatMessages: () => ({ data: mocks.messages, isLoading: false }),
  useCreateChatThread: () => ({ mutateAsync: mocks.createThread, isPending: false }),
  useSendChatTurn: () => ({ mutate: mocks.sendTurn, isPending: false }),
}))

import { ChatWidget } from '@/components/chat/ChatWidget'

function makeThread(overrides: Partial<(typeof mocks.threads)[number]> = {}) {
  return {
    id: 't1',
    title: null,
    status: 'collecting',
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: '2026-01-01T00:00:00.000Z',
    ...overrides,
  }
}

beforeEach(() => {
  mocks.sendTurn.mockReset()
  mocks.createThread.mockReset()
  mocks.createThread.mockResolvedValue(makeThread({ id: 'new-thread', status: 'idle' }))
  mocks.pathname = '/dashboard'
  mocks.threads = []
  mocks.messages = []
})

describe('ChatWidget — gating & drawer', () => {
  it('renders the FAB on an authenticated private page', () => {
    render(<ChatWidget />)
    expect(screen.getByLabelText('Open chat assistant')).toBeInTheDocument()
  })

  it('opens the drawer and hides the FAB when the FAB is clicked', () => {
    mocks.threads = [makeThread()]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))

    expect(screen.getByLabelText('Message the assistant')).toBeInTheDocument()
    expect(screen.queryByLabelText('Open chat assistant')).not.toBeInTheDocument()
  })
})

describe('ChatWidget — sending turns', () => {
  it('posts { message, context } with event_uid on an event route', async () => {
    mocks.pathname = '/events/evt-123'
    mocks.threads = [makeThread({ id: 't1', status: 'collecting' })]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))

    const input = screen.getByLabelText('Message the assistant')
    fireEvent.change(input, { target: { value: 'Find us a time' } })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => expect(mocks.sendTurn).toHaveBeenCalledTimes(1))
    expect(mocks.sendTurn).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Find us a time',
        context: { page: 'event', event_uid: 'evt-123' },
      }),
      expect.anything()
    )
    // No structured action rides along with a plain text message.
    expect(mocks.sendTurn.mock.calls[0][0]).not.toHaveProperty('action')
  })

  it('posts the exact structured action (no free text) when a button is clicked', async () => {
    mocks.pathname = '/events/evt-9'
    mocks.threads = [makeThread({ id: 't2', status: 'awaiting_choice' })]
    mocks.messages = [
      {
        id: 'm1',
        thread_id: 't2',
        role: 'assistant',
        content: 'Would you like to book directly?',
        payload: {
          card: null,
          buttons: [{ label: 'Book directly', action: { type: 'book_direct' } }],
        },
        created_at: '2026-01-02T00:00:00.000Z',
      },
    ]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    fireEvent.click(await screen.findByText('Book directly'))

    await waitFor(() => expect(mocks.sendTurn).toHaveBeenCalledTimes(1))
    expect(mocks.sendTurn).toHaveBeenCalledWith(
      expect.objectContaining({
        action: { type: 'book_direct' },
        context: { page: 'event', event_uid: 'evt-9' },
      }),
      expect.anything()
    )
    // The action is sent structurally — never encoded as a free-text message.
    expect(mocks.sendTurn.mock.calls[0][0]).not.toHaveProperty('message')
  })
})
