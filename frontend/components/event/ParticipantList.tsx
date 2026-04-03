'use client'

import { Star, X } from 'lucide-react'
import { useParticipants, useRemoveParticipant, useUpdatePermissions } from '@/hooks/useParticipants'
import type { Participant } from '@/types'

function RsvpBadge({ status, rsvpStatus }: { status: string; rsvpStatus: string | null }) {
  const display = rsvpStatus ?? status
  const styles: Record<string, string> = {
    going: 'bg-secondary-container text-on-secondary-container',
    accepted: 'bg-secondary-container text-on-secondary-container',
    maybe: 'bg-surface-container-high text-on-surface-variant',
    not_going: 'bg-error-container text-on-error-container',
    pending: 'bg-surface-container-high text-on-surface-variant',
    invited: 'bg-surface-container-high text-on-surface-variant',
    declined: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${styles[display] ?? styles.pending}`}>
      {display.replace('_', ' ')}
    </span>
  )
}

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
    return <div className="text-sm text-on-surface-variant">Loading participants…</div>
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
