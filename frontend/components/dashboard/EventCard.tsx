import Link from 'next/link'
import { Calendar, ArrowRight } from 'lucide-react'
import { formatDateWindow } from '@/lib/dates'
import { EventTypeBadge } from './EventTypeBadge'
import { StatusBadge } from './StatusBadge'
import { ParticipantAvatars } from './ParticipantAvatars'
import type { EventWithParticipants } from '@/types'

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
