'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { useProposalNotes, useCreateProposalNote, useDeleteProposalNote } from '@/hooks/useProposalNotes'
import { formatTime } from '@/lib/dates'

export function ProposalNotes({
  eventUid,
  proposedTimeId,
  currentUserId,
}: {
  eventUid: string
  proposedTimeId: string
  currentUserId: string
}) {
  const [draft, setDraft] = useState('')

  const { notes, isLoading } = useProposalNotes(eventUid, proposedTimeId)
  const { mutate: createNote, isPending: isCreating } = useCreateProposalNote(eventUid, proposedTimeId)
  const { mutate: deleteNote } = useDeleteProposalNote(eventUid, proposedTimeId)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const content = draft.trim()
    if (!content) return
    createNote({ content }, { onSuccess: () => setDraft('') })
  }

  return (
    <div className="space-y-3">
      {/* Note list */}
      {isLoading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="animate-pulse space-y-1">
              <div className="h-2.5 rounded bg-surface-container-high w-24" />
              <div className="h-3 rounded bg-surface-container-high w-full" />
            </div>
          ))}
        </div>
      ) : !notes || notes.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No notes yet.</p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <div key={note.id} className="flex items-start justify-between gap-2 group">
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant/60 truncate">
                  {note.user_id.slice(0, 8)} · {formatTime(note.created_at)}
                </p>
                <p className="text-sm text-on-surface leading-snug">{note.content}</p>
              </div>
              {note.user_id === currentUserId && (
                <button
                  onClick={() => deleteNote(note.id)}
                  className="p-1 rounded-full hover:bg-error-container/50 text-on-surface-variant hover:text-on-error-container transition-colors shrink-0 opacity-0 group-hover:opacity-100"
                  title="Delete note"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add note form */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-1">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note…"
          className="flex-1 min-w-0 text-sm bg-surface-container rounded-lg px-3 py-1.5 text-on-surface placeholder:text-on-surface-variant/50 outline-none focus:ring-2 focus:ring-primary/30 transition-shadow"
        />
        <button
          type="submit"
          disabled={!draft.trim() || isCreating}
          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-primary text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:pointer-events-none shrink-0"
        >
          Add
        </button>
      </form>
    </div>
  )
}
