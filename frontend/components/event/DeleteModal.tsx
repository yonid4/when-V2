'use client'

import { useRouter } from 'next/navigation'
import { Trash2 } from 'lucide-react'
import { useDeleteEvent } from '@/hooks/useEvent'
import type { EventWithParticipants } from '@/types'

export function DeleteModal({
  event,
  onClose,
}: {
  event: EventWithParticipants
  onClose: () => void
}) {
  const router = useRouter()
  const { mutate: deleteEvent, isPending } = useDeleteEvent()

  function handleDelete() {
    deleteEvent(event.uid, {
      onSuccess: () => {
        router.refresh()
        router.push('/dashboard')
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-md shadow-warm-md">
        <div className="p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-error-container flex items-center justify-center mx-auto">
            <Trash2 className="w-6 h-6 text-on-error-container" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-on-surface">Delete Event</h2>
            <p className="text-sm text-on-surface-variant mt-2">
              Are you sure you want to delete{' '}
              <span className="font-semibold text-on-surface">"{event.name}"</span>? All participants
              will be notified. This action cannot be undone.
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold hover:bg-surface-container transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isPending}
              className="flex-1 py-3 rounded-xl bg-error text-on-error font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:-translate-y-0.5 transition-all duration-300"
            >
              <Trash2 className="w-4 h-4" />
              {isPending ? 'Deleting…' : 'Delete Event'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
