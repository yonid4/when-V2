'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { MessageSquare, Plus, X } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import {
  useChatThreads,
  useChatMessages,
  useCreateChatThread,
  useSendChatTurn,
} from '@/hooks/useChat'
import type { ChatActionPayload, ChatPageContext, ChatTurnRequest } from '@/types'
import { MessageList } from './MessageList'
import { DraftEventCard } from './DraftEventCard'
import { ChatInput } from './ChatInput'

// Keep in sync with PUBLIC_PATHS in app/providers.tsx — on these paths a visitor
// may be unauthenticated and the widget must stay hidden.
const PUBLIC_PATHS = ['/', '/auth/callback', '/privacy', '/terms']

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
  const [isOpen, setIsOpen] = useState(false)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const bootstrappedRef = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const threadsQuery = useChatThreads()
  const messagesQuery = useChatMessages(activeThreadId ?? '')
  const createThread = useCreateChatThread()
  const sendTurn = useSendChatTurn(activeThreadId ?? '')

  const threads = threadsQuery.data ?? []
  const messages = messagesQuery.data ?? []
  const context = deriveChatContext(pathname)

  const activeThread = activeThreadId
    ? threads.find((thread) => thread.id === activeThreadId) ?? null
    : null
  const awaitsInput = activeThread ? activeThread.status !== 'idle' : false

  // The draft card + action buttons come from the most recent assistant turn.
  const latestAssistant = [...messages].reverse().find((m) => m.role === 'assistant') ?? null
  const card = latestAssistant?.payload?.card ?? null
  const buttons = awaitsInput ? latestAssistant?.payload?.buttons ?? [] : []

  // Auto-create / reuse the most recent thread the first time the drawer opens.
  useEffect(() => {
    if (!isOpen || activeThreadId || bootstrappedRef.current) return
    if (threadsQuery.isLoading) return
    bootstrappedRef.current = true
    const mostRecent = [...threads].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0]
    if (mostRecent) {
      setActiveThreadId(mostRecent.id)
    } else {
      createThread
        .mutateAsync()
        .then((thread) => setActiveThreadId(thread.id))
        .catch(() => {
          bootstrappedRef.current = false
        })
    }
  }, [isOpen, activeThreadId, threads, threadsQuery.isLoading, createThread])

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
  }, [isOpen, messages.length, card])

  function dispatchTurn(body: ChatTurnRequest) {
    if (!activeThreadId) return
    setNotice(null)
    sendTurn.mutate(body, {
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
    dispatchTurn({ message, context })
  }

  function handleAction(action: ChatActionPayload) {
    dispatchTurn({ action, context })
  }

  async function handleNewChat() {
    setNotice(null)
    try {
      const thread = await createThread.mutateAsync()
      bootstrappedRef.current = true
      setActiveThreadId(thread.id)
    } catch {
      setNotice('Could not start a new chat. Please try again.')
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
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
          onClick={() => setIsOpen(false)}
          aria-label="Close chat"
          className="p-2 rounded-full text-on-surface-variant hover:bg-surface-container transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      {/* Body: scrollable message history + inline draft card */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
        <MessageList messages={messages} isLoading={messagesQuery.isLoading && !!activeThreadId} />

        {card && (
          <DraftEventCard
            card={card}
            buttons={buttons}
            disabled={sendTurn.isPending}
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
                  disabled={sendTurn.isPending}
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
        <ChatInput disabled={sendTurn.isPending} onSend={handleSend} />
      </div>
    </div>
  )
}
