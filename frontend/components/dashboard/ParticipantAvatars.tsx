import type { EventWithParticipants } from '@/types'

export function ParticipantAvatars({ participants }: { participants: EventWithParticipants['participants'] }) {
  const visible = participants.slice(0, 4)
  const overflow = participants.length - visible.length

  return (
    <div className="flex items-center">
      <div className="flex -space-x-2">
        {visible.map((p) => (
          <div
            key={p.user_id}
            className="w-7 h-7 rounded-full ring-2 ring-surface-container-lowest bg-surface-container-high flex items-center justify-center overflow-hidden"
            title={p.full_name ?? p.email_address ?? ''}
          >
            {p.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={p.avatar_url} alt={p.full_name ?? ''} className="w-full h-full object-cover" />
            ) : (
              <span className="text-xs font-bold text-on-surface-variant">
                {(p.full_name ?? p.email_address ?? '?')[0].toUpperCase()}
              </span>
            )}
          </div>
        ))}
        {overflow > 0 && (
          <div className="w-7 h-7 rounded-full ring-2 ring-surface-container-lowest bg-surface-container-highest flex items-center justify-center">
            <span className="text-xs font-bold text-on-surface-variant">+{overflow}</span>
          </div>
        )}
      </div>
    </div>
  )
}
