'use client'

import type { ChatMessage } from '@/types'
import { MessageBubble } from './MessageBubble'

interface MessageListProps {
  messages: ChatMessage[]
  isLoading: boolean
  isThinking?: boolean
}

/**
 * The assistant's opening line, shown at the top of every conversation on every
 * page. It is rendered client-side and never persisted, so it costs no turn and
 * never reaches the agent as history — the greeting asks a question the agent
 * doesn't need to be told about. The placeholder id/thread_id/created_at exist
 * only to reuse MessageBubble; nothing reads them.
 */
export const GREETING_MESSAGE: ChatMessage = {
  id: 'greeting',
  thread_id: '',
  role: 'assistant',
  content:
    "Hi! How can I help? Tell me what you'd like to schedule and who to invite, " +
    "and I'll find a time that works for everyone.",
  created_at: '',
}

/**
 * Renders the conversation as a vertical stack of bubbles — the greeting first,
 * then the persisted turns — plus a typing indicator while a turn is in flight.
 * Scrolling and the inline draft card are owned by the parent (ChatWidget) so the
 * card scrolls together with the message history.
 */
export function MessageList({ messages, isLoading, isThinking = false }: MessageListProps) {
  if (isLoading && messages.length === 0) {
    return (
      <div className="space-y-3">
        <div className="h-10 w-2/3 rounded-2xl bg-surface-container-high animate-pulse" />
        <div className="h-10 w-1/2 ml-auto rounded-2xl bg-surface-container-high animate-pulse" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <MessageBubble message={GREETING_MESSAGE} />
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {isThinking && <ThinkingBubble />}
    </div>
  )
}

/** Assistant-side typing-dots bubble shown while a turn is in flight. */
function ThinkingBubble() {
  return (
    <div className="flex justify-start" role="status" aria-label="Assistant is thinking">
      <div className="bg-surface-container-high rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant/70 animate-bounce" />
        <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant/70 animate-bounce [animation-delay:150ms]" />
        <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant/70 animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  )
}
