import Link from 'next/link'
import { Calendar, ArrowRight } from 'lucide-react'
import type { EventWithParticipants } from '@/types'

function formatDateWindow(earliest: string, latest: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return `${fmt(earliest)} – ${fmt(latest)}`
}

const EVENT_TYPE_STYLES: Record<string, string> = {
  meeting: 'bg-blue-100 text-blue-700',
  social: 'bg-purple-100 text-purple-700',
  birthday: 'bg-pink-100 text-pink-700',
  other: 'bg-gray-100 text-gray-600',
}

function EventTypeBadge({ type }: { type: string }) {
  const typeStyle = EVENT_TYPE_STYLES[type?.toLowerCase()] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${typeStyle}`}>
      {type}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: 'bg-secondary-container text-on-secondary-container',
    planning: 'bg-surface-container-high text-on-surface-variant',
    cancelled: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`text-xs font-semibold capitalize px-2 py-0.5 rounded-full ${styles[status] ?? styles.planning}`}>
      {status}
    </span>
  )
}

function ParticipantAvatars({ participants }: { participants: EventWithParticipants['participants'] }) {
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

export default function EventCard({ event }: { event: EventWithParticipants }) {
  return (
    <Link href={`/events/${event.uid}`} className="group block">
      <div className="bg-surface-container-lowest rounded-2xl p-5 flex flex-col gap-3 transition-all duration-500 group-hover:-translate-y-1 group-hover:shadow-warm-md h-full">
        {/* Top row: type + status badges */}
        <div className="flex items-center justify-between">
          <EventTypeBadge type={event.event_type} />
          <StatusBadge status={event.status} />
        </div>

        {/* Event name */}
        <h3 className="text-on-surface font-bold text-lg leading-snug line-clamp-3">
          {event.name}
        </h3>

        {/* Date window */}
        <div className="flex items-center gap-1.5 text-sm text-on-surface-variant">
          <Calendar className="w-4 h-4 shrink-0" />
          <span>{formatDateWindow(event.earliest_datetime_utc, event.latest_datetime_utc)}</span>
        </div>

        {/* Bottom row: avatars + arrow */}
        <div className="flex items-center justify-between mt-auto pt-1">
          <ParticipantAvatars participants={event.participants} />
          <ArrowRight className="w-5 h-5 text-on-surface-variant transition-transform duration-300 group-hover:translate-x-1" />
        </div>
      </div>
    </Link>
  )
}
