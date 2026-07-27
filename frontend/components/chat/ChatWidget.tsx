'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { History, MessageSquare, Plus, Trash2, X } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useChatUiStore } from '@/stores/chatStore'
import {
  useChatThreads,
  useChatMessages,
  useCreateChatThread,
  useSendChatTurn,
  useDeleteChatThread,
} from '@/hooks/useChat'
import { formatRelativeTime } from '@/lib/dates'
import type { ChatActionPayload, ChatPageContext, ChatTurnRequest, ChatTurnResponse } from '@/types'
import { MessageList } from './MessageList'
import { DraftEventCard } from './DraftEventCard'
import { ChatInput } from './ChatInput'

// Keep in sync with PUBLIC_PATHS in app/providers.tsx — on these paths a visitor
// may be unauthenticated and the widget must stay hidden.
const PUBLIC_PATHS = ['/', '/auth/callback', '/privacy', '/terms']

// The active thread is remembered for the browser SESSION only: a reload or a
// route change resumes the same conversation, while a fresh visit to the site
// starts a new chat. sessionStorage (not localStorage) is exactly that lifetime.
const SESSION_THREAD_KEY = 'when.chat.sessionThreadId'

function readSessionThreadId(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_THREAD_KEY)
  } catch {
    // Storage can be unavailable (private mode, blocked cookies) — the chat then
    // simply starts fresh on each page load instead of failing.
    return null
  }
}

function writeSessionThreadId(threadId: string | null) {
  try {
    if (threadId) window.sessionStorage.setItem(SESSION_THREAD_KEY, threadId)
    else window.sessionStorage.removeItem(SESSION_THREAD_KEY)
  } catch {
    /* see readSessionThreadId */
  }
}

/**
 * Derive the page context sent with every chat turn.
 * `/events/{uid}` → event; `/dashboard` → dashboard; everything else → other.
 */
export function deriveChatContext(pathname: string): ChatPageContext {
  const eventMatch = pathname.match(/^\/events\/([^/]+)/)
  if (eventMatch) return { page: 'event', event_uid: eventMatch[1] }
  if (pathname === '/dashboard') return { page: 'dashboard' }
  return { page: 'other' }
}

/**
 * Gate: the widget renders nothing for unauthenticated users or on public
 * paths. All chat data hooks live in the inner component so they never fire
 * until the user is authenticated on a private page.
 */
export function ChatWidget() {
  const pathname = usePathname()
  const user = useAuthStore((s) => s.user)

  if (!user) return null
  if (PUBLIC_PATHS.includes(pathname)) return null

  return <ChatWidgetInner pathname={pathname} />
}

function ChatWidgetInner({ pathname }: { pathname: string }) {
  const router = useRouter()
  const isOpen = useChatUiStore((s) => s.isOpen)
  const setOpen = useChatUiStore((s) => s.setOpen)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  // Bumped to send the caret back to the composer; see ChatInput's focusSignal.
  const [composerFocusSignal, setComposerFocusSignal] = useState(0)
  const bootstrappedRef = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const threadsQuery = useChatThreads()
  const messagesQuery = useChatMessages(activeThreadId ?? '')
  const createThread = useCreateChatThread()
  const sendTurn = useSendChatTurn()
  const deleteThread = useDeleteChatThread()

  const threads = threadsQuery.data ?? []
  const messages = messagesQuery.data ?? []
  const context = deriveChatContext(pathname)
  const sortedThreads = [...threads].sort((a, b) => b.updated_at.localeCompare(a.updated_at))

  const activeThread = activeThreadId
    ? threads.find((thread) => thread.id === activeThreadId) ?? null
    : null
  const awaitsInput = activeThread ? activeThread.status !== 'idle' : false
  // A first message spans two requests (create thread → run turn); both count as
  // the turn being in flight.
  const turnInFlight = sendTurn.isPending || createThread.isPending

  // The draft card + action buttons come from the most recent assistant turn.
  const latestAssistant = [...messages].reverse().find((m) => m.role === 'assistant') ?? null
  const card = latestAssistant?.payload?.card ?? null
  const buttons = awaitsInput ? latestAssistant?.payload?.buttons ?? [] : []

  // Resume this browser session's conversation the first time the drawer opens.
  // A session that has none — i.e. a first visit — starts a new chat instead of
  // reopening the last one; the thread row itself is created lazily on the first
  // message, so merely opening the drawer never leaves an empty conversation
  // behind. The stored id is re-checked against the thread list so one deleted
  // elsewhere doesn't resurrect.
  useEffect(() => {
    if (!isOpen || activeThreadId || bootstrappedRef.current) return
    if (threadsQuery.isLoading) return
    bootstrappedRef.current = true
    const sessionThreadId = readSessionThreadId()
    const stillExists = (threadsQuery.data ?? []).some((thread) => thread.id === sessionThreadId)
    if (sessionThreadId && stillExists) {
      setActiveThreadId(sessionThreadId)
    } else {
      writeSessionThreadId(null)
    }
  }, [isOpen, activeThreadId, threadsQuery.data, threadsQuery.isLoading])

  // Keep the newest message / card in view.
  useEffect(() => {
    const el = bottomRef.current
    if (isOpen && el && typeof el.scrollIntoView === 'function') {
      try {
        el.scrollIntoView({ block: 'end' })
      } catch {
        /* scrollIntoView is a no-op in some environments (e.g. jsdom) */
      }
    }
  }, [isOpen, messages.length, card, turnInFlight])

  /** Set the active thread and remember it for the rest of this browser session. */
  function selectThread(threadId: string | null) {
    setActiveThreadId(threadId)
    writeSessionThreadId(threadId)
  }

  async function dispatchTurn(body: ChatTurnRequest) {
    setNotice(null)
    // A fresh chat has no thread row yet — the first message creates it.
    let threadId = activeThreadId
    if (!threadId) {
      try {
        const thread = await createThread.mutateAsync()
        threadId = thread.id
        selectThread(thread.id)
      } catch {
        setNotice('Could not start a new chat. Please try again.')
        return
      }
    }
    sendTurn.mutate({ threadId, ...body }, {
      // A brand-new event was created this turn — close the drawer and open its
      // page so the user lands on the event they just made. Edits don't set this.
      onSuccess: (response: ChatTurnResponse) => {
        if (response.created_event_uid) {
          setOpen(false)
          router.push(`/events/${response.created_event_uid}`)
        }
      },
      onError: (err: unknown) => {
        const detail = (err as { detail?: string })?.detail
        setNotice(
          detail === 'chat_disabled'
            ? 'The chat assistant is currently unavailable. Please try again later.'
            : 'Something went wrong. Please try again.'
        )
      },
    })
  }

  function handleSend(message: string) {
    void dispatchTurn({ message, context })
  }

  function handleAction(action: ChatActionPayload) {
    void dispatchTurn({ action, context })
  }

  // Clears the conversation back to the greeting; the thread row is created when
  // the user actually sends something.
  function handleNewChat() {
    setNotice(null)
    setShowHistory(false)
    bootstrappedRef.current = true
    selectThread(null)
    setComposerFocusSignal((prev) => prev + 1)
  }

  function handleSelectThread(threadId: string) {
    setNotice(null)
    selectThread(threadId)
    setShowHistory(false)
    setConfirmDeleteId(null)
  }

  async function handleDeleteThread(threadId: string) {
    setConfirmDeleteId(null)
    try {
      await deleteThread.mutateAsync(threadId)
      if (threadId === activeThreadId) {
        // Fall back to the next most recent thread; start fresh when none left.
        const next = sortedThreads.find((thread) => thread.id !== threadId)
        selectThread(next ? next.id : null)
      }
    } catch {
      setNotice('Could not delete the chat. Please try again.')
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open chat assistant"
        className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-primary text-on-primary shadow-[0_12px_28px_-8px_rgba(155,68,40,0.45)] flex items-center justify-center hover:bg-primary/90 transition-colors"
      >
        <MessageSquare className="w-6 h-6" />
      </button>
    )
  }

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[400px] bg-surface-container-low border-l border-outline-variant/20 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.15)] flex flex-col">
      {/* Header */}
      <header className="flex items-center gap-1 px-4 py-3 border-b border-outline-variant/20 bg-surface-container-lowest shrink-0">
        <h2 className="flex-1 text-sm font-extrabold text-on-surface">Assistant</h2>
        <button
          type="button"
          onClick={() => setShowHistory((prev) => !prev)}
          aria-label="Chat history"
          aria-expanded={showHistory}
          className={`p-2 rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors ${
            showHistory ? 'bg-surface-container' : ''
          }`}
        >
          <History className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleNewChat}
          disabled={createThread.isPending}
          aria-label="New chat"
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-60"
        >
          <Plus className="w-4 h-4" />
          New chat
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close chat"
          className="p-2 rounded-full text-on-surface-variant hover:bg-surface-container transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      {/* Thread history panel — toggled from the header, sits above messages */}
      {showHistory && (
        <div className="shrink-0 max-h-64 overflow-y-auto border-b border-outline-variant/20 bg-surface-container-lowest">
          {sortedThreads.length === 0 && (
            <p className="px-4 py-3 text-xs text-on-surface-variant">No previous chats yet.</p>
          )}
          {sortedThreads.map((thread) => (
            <div
              key={thread.id}
              className={`flex items-center gap-2 px-4 py-2 hover:bg-surface-container transition-colors ${
                thread.id === activeThreadId ? 'bg-primary/10' : ''
              }`}
            >
              <button
                type="button"
                onClick={() => handleSelectThread(thread.id)}
                className="flex-1 min-w-0 text-left"
              >
                <span className="block truncate text-xs font-bold text-on-surface">
                  {thread.title || 'New conversation'}
                </span>
                <span className="block text-[10px] text-on-surface-variant">
                  {formatRelativeTime(thread.updated_at)}
                </span>
              </button>
              {confirmDeleteId === thread.id ? (
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleDeleteThread(thread.id)}
                    disabled={deleteThread.isPending}
                    aria-label="Confirm delete"
                    className="px-2 py-1 rounded-lg text-[10px] font-bold text-on-error-container bg-error-container hover:bg-error-container/80 transition-colors disabled:opacity-60"
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(null)}
                    aria-label="Cancel delete"
                    className="px-2 py-1 rounded-lg text-[10px] font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmDeleteId(thread.id)}
                  aria-label="Delete chat"
                  className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Body: scrollable message history + inline draft card */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
        <MessageList
          messages={messages}
          isLoading={messagesQuery.isLoading && !!activeThreadId}
          isThinking={turnInFlight}
        />

        {card && (
          <DraftEventCard
            card={card}
            buttons={buttons}
            disabled={turnInFlight}
            onAction={handleAction}
          />
        )}

        {!card && buttons.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {buttons.map((button) => {
              const isCancel = button.action.type === 'cancel'
              return (
                <button
                  key={`${button.action.type}-${button.label}`}
                  type="button"
                  onClick={() => handleAction(button.action)}
                  disabled={turnInFlight}
                  className={`flex-1 min-w-[96px] py-2.5 px-3 rounded-xl text-sm font-bold transition-colors disabled:opacity-60 ${
                    isCancel
                      ? 'border border-outline-variant text-on-surface-variant hover:bg-surface-container'
                      : 'bg-primary text-on-primary hover:bg-primary/90'
                  }`}
                >
                  {button.label}
                </button>
              )
            })}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Inline notice (e.g. 503 chat_disabled) */}
      {notice && (
        <div className="px-4 py-2 text-xs font-semibold text-on-error-container bg-error-container/60 border-t border-outline-variant/20 shrink-0">
          {notice}
        </div>
      )}

      {/* Footer composer */}
      <div className="shrink-0">
        <ChatInput
          disabled={turnInFlight}
          onSend={handleSend}
          focusSignal={composerFocusSignal}
        />
      </div>
    </div>
  )
}
