'use client'

import { Star, X } from 'lucide-react'
import { useParticipants, useRemoveParticipant, useUpdatePermissions } from '@/hooks/useParticipants'
import type { Participant } from '@/types'
import RsvpBadge from '@/components/event/RsvpBadge'

export function ParticipantList({
  uid,
  coordinatorId,
  currentUserId,
}: {
  uid: string
  coordinatorId: string
  currentUserId: string
}) {
  const { data: participants, isLoading } = useParticipants(uid)
  const { mutate: removeParticipant } = useRemoveParticipant(uid)
  const { mutate: updatePermissions } = useUpdatePermissions(uid)

  const isCoordinator = currentUserId === coordinatorId

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 animate-pulse">
            <div className="w-10 h-10 rounded-full bg-surface-container-high shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 rounded bg-surface-container-high w-32" />
              <div className="h-2.5 rounded bg-surface-container-high w-20" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!participants || participants.length === 0) {
    return <div className="text-sm text-on-surface-variant">No participants yet.</div>
  }

  return (
    <div className="space-y-3">
      {participants.map((p: Participant) => {
        const isCoord = p.user_id === coordinatorId
        const isSelf = p.user_id === currentUserId
        return (
          <div key={p.user_id} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 min-w-0">
              <div className="relative shrink-0">
                <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center overflow-hidden ring-2 ring-surface-container-lowest">
                  {p.avatar_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.avatar_url} alt={p.full_name ?? ''} className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-sm font-bold text-on-surface-variant">
                      {(p.full_name ?? p.email_address ?? '?')[0].toUpperCase()}
                    </span>
                  )}
                </div>
                {isCoord && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-tertiary-container text-on-tertiary-container rounded-full flex items-center justify-center">
                    <Star className="w-2.5 h-2.5" />
                  </span>
                )}
              </div>
              <div className="min-w-0">
                <p className="font-bold text-sm text-on-surface truncate">{p.full_name ?? p.email_address}</p>
                {isCoord && (
                  <p className="text-[10px] uppercase tracking-widest text-primary font-bold">Coordinator</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <RsvpBadge status={p.status} rsvpStatus={p.rsvp_status} />

              {isCoordinator && !isCoord && (
                <>
                  <button
                    onClick={() => updatePermissions({ userId: p.user_id, can_invite: !p.can_invite })}
                    title={p.can_invite ? 'Revoke invite permission' : 'Allow to invite'}
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-colors ${
                      p.can_invite
                        ? 'bg-primary/10 text-primary'
                        : 'bg-surface-container-high text-on-surface-variant hover:bg-primary/10 hover:text-primary'
                    }`}
                  >
                    {p.can_invite ? 'CAN INVITE' : 'INVITE OFF'}
                  </button>
                  <button
                    onClick={() => removeParticipant(p.user_id)}
                    className="p-1 rounded-full hover:bg-error-container/50 text-on-surface-variant hover:text-on-error-container transition-colors"
                    title="Remove participant"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </>
              )}

              {!isCoordinator && isSelf && (
                <button
                  onClick={() => removeParticipant(p.user_id)}
                  className="p-1 rounded-full hover:bg-error-container/50 text-on-surface-variant hover:text-on-error-container transition-colors"
                  title="Leave event"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
