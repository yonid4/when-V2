'use client'

import { useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  disabled: boolean
  onSend: (message: string) => void
}

/**
 * Message composer for the chat drawer. Submits on Enter (Shift+Enter inserts a
 * newline) or via the send button. Trims and drops empty input; parent decides
 * how the message is dispatched.
 */
export function ChatInput({ disabled, onSend }: ChatInputProps) {
  const [value, setValue] = useState('')

  const canSend = value.trim().length > 0 && !disabled

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="flex items-end gap-2 p-3 border-t border-outline-variant/20 bg-surface-container-lowest"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        placeholder="Message the assistant…"
        aria-label="Message the assistant"
        className="flex-1 resize-none bg-surface-container-low rounded-xl px-3 py-2.5 max-h-32 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm font-medium text-on-surface disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={!canSend}
        aria-label="Send message"
        className="shrink-0 w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center hover:bg-primary/90 transition-colors disabled:opacity-40"
      >
        <Send className="w-4 h-4" />
      </button>
    </form>
  )
}
