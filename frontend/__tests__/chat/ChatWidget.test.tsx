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
  sendPending: false,
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  push: vi.fn(),
  messagesThreadId: '',
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
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: unknown }) => unknown) =>
    selector({ user: { id: 'u1', email_address: 'me@example.com' } }),
}))

vi.mock('@/hooks/useChat', () => ({
  useChatThreads: () => ({ data: mocks.threads, isLoading: false }),
  useChatMessages: (threadId: string) => {
    mocks.messagesThreadId = threadId
    return { data: mocks.messages, isLoading: false }
  },
  useCreateChatThread: () => ({ mutateAsync: mocks.createThread, isPending: false }),
  useSendChatTurn: () => ({ mutate: mocks.sendTurn, isPending: mocks.sendPending }),
  useDeleteChatThread: () => ({ mutateAsync: mocks.deleteThread, isPending: false }),
}))

import { ChatWidget } from '@/components/chat/ChatWidget'
import { useChatUiStore } from '@/stores/chatStore'

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
  mocks.deleteThread.mockReset()
  mocks.push.mockReset()
  mocks.createThread.mockResolvedValue(makeThread({ id: 'new-thread', status: 'idle' }))
  mocks.deleteThread.mockResolvedValue(undefined)
  mocks.sendPending = false
  mocks.messagesThreadId = ''
  mocks.pathname = '/dashboard'
  mocks.threads = []
  mocks.messages = []
  // The drawer's open state lives in a real (module-level) zustand store —
  // reset it so a drawer opened in one test doesn't leak into the next.
  useChatUiStore.setState({ isOpen: false })
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

  it('navigates to the new event and closes the drawer when created_event_uid is returned', async () => {
    mocks.threads = [makeThread({ id: 't3', status: 'awaiting_confirmation' })]
    mocks.messages = [
      {
        id: 'm1',
        thread_id: 't3',
        role: 'assistant',
        content: "I'll set it up in When and invite everyone. Confirm to create it.",
        payload: {
          card: null,
          buttons: [{ label: 'Confirm', action: { type: 'confirm_draft' } }],
        },
        created_at: '2026-01-02T00:00:00.000Z',
      },
    ]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    fireEvent.click(await screen.findByText('Confirm'))

    await waitFor(() => expect(mocks.sendTurn).toHaveBeenCalledTimes(1))
    // The turn's onSuccess is what drives navigation; fire it with a created event.
    const onSuccess = mocks.sendTurn.mock.calls[0][1].onSuccess
    onSuccess({ created_event_uid: 'evt-new' })

    expect(mocks.push).toHaveBeenCalledWith('/events/evt-new')
    expect(useChatUiStore.getState().isOpen).toBe(false)
  })

  it('does not navigate when no event was created this turn', async () => {
    mocks.threads = [makeThread({ id: 't4', status: 'collecting' })]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    const input = screen.getByLabelText('Message the assistant')
    fireEvent.change(input, { target: { value: 'Lunch on Friday' } })
    fireEvent.click(screen.getByLabelText('Send message'))

    await waitFor(() => expect(mocks.sendTurn).toHaveBeenCalledTimes(1))
    // A turn that only advances the draft (no created_event_uid) never navigates.
    mocks.sendTurn.mock.calls[0][1].onSuccess({ event_uid: null, created_event_uid: null })

    expect(mocks.push).not.toHaveBeenCalled()
  })
})

describe('ChatWidget — thinking indicator', () => {
  it('shows the typing indicator while a turn is in flight', () => {
    mocks.sendPending = true
    mocks.threads = [makeThread()]
    mocks.messages = [
      {
        id: 'm1',
        thread_id: 't1',
        role: 'user',
        content: 'Find us a time',
        created_at: '2026-07-19T10:00:00Z',
      },
    ]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))

    expect(screen.getByLabelText('Assistant is thinking')).toBeInTheDocument()
  })

  it('hides the typing indicator when no turn is in flight', () => {
    mocks.threads = [makeThread()]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))

    expect(screen.queryByLabelText('Assistant is thinking')).not.toBeInTheDocument()
  })
})

describe('ChatWidget — thread history', () => {
  const twoThreads = () => [
    makeThread({ id: 't1', title: 'Dinner with team', updated_at: '2026-07-18T12:00:00.000Z' }),
    makeThread({ id: 't2', title: 'Board games night', updated_at: '2026-07-17T12:00:00.000Z' }),
  ]

  it('lists previous threads and switches the active thread on click', async () => {
    mocks.threads = twoThreads()
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    // Bootstrap resumes the most recently updated thread.
    await waitFor(() => expect(mocks.messagesThreadId).toBe('t1'))

    fireEvent.click(screen.getByLabelText('Chat history'))
    fireEvent.click(screen.getByText('Board games night'))

    await waitFor(() => expect(mocks.messagesThreadId).toBe('t2'))
    // Panel closes after selecting.
    expect(screen.queryByText('Dinner with team')).not.toBeInTheDocument()
  })

  it('falls back to "New conversation" for untitled threads', () => {
    mocks.threads = [makeThread({ id: 't1', title: null })]
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    fireEvent.click(screen.getByLabelText('Chat history'))

    expect(screen.getByText('New conversation')).toBeInTheDocument()
  })

  it('deletes a thread only after confirmation', async () => {
    mocks.threads = twoThreads()
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    fireEvent.click(screen.getByLabelText('Chat history'))

    // Rows are sorted most-recent first: [t1, t2] — target t2.
    fireEvent.click(screen.getAllByLabelText('Delete chat')[1])
    expect(mocks.deleteThread).not.toHaveBeenCalled()

    fireEvent.click(screen.getByLabelText('Confirm delete'))

    await waitFor(() => expect(mocks.deleteThread).toHaveBeenCalledWith('t2'))
  })

  it('does not delete when the confirmation is cancelled', () => {
    mocks.threads = twoThreads()
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    fireEvent.click(screen.getByLabelText('Chat history'))
    fireEvent.click(screen.getAllByLabelText('Delete chat')[0])
    fireEvent.click(screen.getByLabelText('Cancel delete'))

    expect(mocks.deleteThread).not.toHaveBeenCalled()
    expect(screen.getAllByLabelText('Delete chat')).toHaveLength(2)
  })

  it('switches to the next most recent thread after deleting the active one', async () => {
    mocks.threads = twoThreads()
    render(<ChatWidget />)

    fireEvent.click(screen.getByLabelText('Open chat assistant'))
    await waitFor(() => expect(mocks.messagesThreadId).toBe('t1'))

    fireEvent.click(screen.getByLabelText('Chat history'))
    fireEvent.click(screen.getAllByLabelText('Delete chat')[0])
    fireEvent.click(screen.getByLabelText('Confirm delete'))

    await waitFor(() => expect(mocks.deleteThread).toHaveBeenCalledWith('t1'))
    await waitFor(() => expect(mocks.messagesThreadId).toBe('t2'))
  })
})
