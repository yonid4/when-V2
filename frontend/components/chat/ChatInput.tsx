'use client'

import { useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  disabled: boolean
  onSend: (message: string) => void
  /**
   * Bumped by the parent to hand the caret back to the composer (a new chat was
   * started). Mounting — i.e. the drawer opening — focuses it too.
   */
  focusSignal?: number
}

/**
 * True when nothing in the page holds focus — the state the browser falls into
 * after a focused element is disabled or removed. Focus that sits on a real
 * element (another field, a button the user tabbed to) is left alone.
 */
function isFocusLoose(): boolean {
  const active = document.activeElement
  return !active || active === document.body || active === document.documentElement
}

/**
 * Message composer for the chat drawer. Submits on Enter (Shift+Enter inserts a
 * newline) or via the send button. Trims and drops empty input; parent decides
 * how the message is dispatched.
 *
 * The composer keeps the caret after a send and reclaims focus whenever the
 * page drops it, so typing always continues in the chat box.
 */
export function ChatInput({ disabled, onSend, focusSignal = 0 }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const canSend = value.trim().length > 0 && !disabled

  // Ready to type the moment the drawer opens (mount) or a new chat is started.
  useEffect(() => {
    textareaRef.current?.focus()
  }, [focusSignal])

  // Anything that disables itself while focused (the send button, the draft
  // card's action buttons) hands focus back to <body>. Whenever the turn ends,
  // reclaim it for the composer — but only from <body>, so focus is never
  // stolen from something the user deliberately moved to.
  const wasDisabled = useRef(disabled)
  useEffect(() => {
    const justFinished = wasDisabled.current && !disabled
    wasDisabled.current = disabled
    if (!justFinished) return
    if (isFocusLoose()) textareaRef.current?.focus()
  }, [disabled])

  // Type-to-compose: while the drawer is open, a plain printable keystroke that
  // lands nowhere in particular is routed into the composer, so the user can
  // just keep typing after a send without clicking back into the box. The
  // character is inserted here rather than left to the browser, which would
  // otherwise drop it (focus moves after the key has already been dispatched).
  useEffect(() => {
    function handleWindowKeyDown(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key.length !== 1) return // printable single characters only
      const el = textareaRef.current
      if (!el || document.activeElement === el) return
      if (!isFocusLoose()) return
      e.preventDefault()
      el.focus()
      setValue((prev) => prev + e.key)
    }
    window.addEventListener('keydown', handleWindowKeyDown)
    return () => window.removeEventListener('keydown', handleWindowKeyDown)
  }, [])

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Keep the caret in the composer so the user can keep typing (and the
    // mobile keyboard stays up) — sending via the button would otherwise leave
    // focus on a button that is about to disable itself.
    textareaRef.current?.focus()
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
      {/* Deliberately never `disabled`: disabling a focused element blurs it, so
          the composer would lose focus for the whole in-flight turn. Sending is
          blocked by `submit()` and the send button instead. */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Message the assistant…"
        aria-label="Message the assistant"
        className="flex-1 resize-none bg-surface-container-low rounded-xl px-3 py-2.5 max-h-32 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm font-medium text-on-surface"
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
