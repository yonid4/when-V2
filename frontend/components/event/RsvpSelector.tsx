'use client'

import { useParticipants, useUpdateRsvp } from '@/hooks/useParticipants'
import type { Participant } from '@/types'

const OPTIONS = [
  { value: 'going', label: 'Going' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'not_going', label: 'Not Going' },
] as const

export function RsvpSelector({
  uid,
  coordinatorId,
  currentUserId,
}: {
  uid: string
  coordinatorId: string
  currentUserId: string
}) {
  const { data: participants } = useParticipants(uid)
  const { mutate: updateRsvp, isPending } = useUpdateRsvp(uid)

  const isCoordinator = currentUserId === coordinatorId
  if (isCoordinator) return null

  const me = participants?.find((p: Participant) => p.user_id === currentUserId)
  if (!me) return null

  const current = me.rsvp_status

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Your RSVP</p>
      <div className="flex gap-2">
        {OPTIONS.map((opt) => {
          const isActive = current === opt.value
          return (
            <button
              key={opt.value}
              onClick={() => updateRsvp({ userId: currentUserId, rsvp_status: opt.value })}
              disabled={isPending}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all duration-200 disabled:opacity-60 ${
                isActive
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
              }`}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
