'use client'

import type { ChatMessage } from '@/types'

/**
 * A single chat message bubble. User messages align right on a primary
 * surface; assistant messages align left on a neutral container surface.
 * Renders nothing when the message has no text content (e.g. an assistant
 * turn that carries only a draft card).
 */
export function MessageBubble({ message }: { message: ChatMessage }) {
  const content = message.content?.trim()
  if (!content) return null

  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm font-medium whitespace-pre-wrap break-words ${
          isUser
            ? 'bg-primary text-on-primary rounded-br-sm'
            : 'bg-surface-container-high text-on-surface rounded-bl-sm'
        }`}
      >
        {content}
      </div>
    </div>
  )
}
