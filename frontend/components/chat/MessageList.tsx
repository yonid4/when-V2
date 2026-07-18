'use client'

import { MessageSquare } from 'lucide-react'
import type { ChatMessage } from '@/types'
import { MessageBubble } from './MessageBubble'

interface MessageListProps {
  messages: ChatMessage[]
  isLoading: boolean
}

/**
 * Renders the conversation as a vertical stack of bubbles. Scrolling and the
 * inline draft card are owned by the parent (ChatWidget) so the card scrolls
 * together with the message history.
 */
export function MessageList({ messages, isLoading }: MessageListProps) {
  if (isLoading && messages.length === 0) {
    return (
      <div className="space-y-3">
        <div className="h-10 w-2/3 rounded-2xl bg-surface-container-high animate-pulse" />
        <div className="h-10 w-1/2 ml-auto rounded-2xl bg-surface-container-high animate-pulse" />
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
          <MessageSquare className="w-6 h-6 text-primary" />
        </div>
        <p className="text-sm font-semibold text-on-surface">How can I help?</p>
        <p className="text-xs text-on-surface-variant max-w-[240px]">
          Ask me to create an event or find a time that works for everyone.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  )
}
