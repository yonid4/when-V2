import Link from 'next/link'
import { CalendarX } from 'lucide-react'

export default function EventNotFound() {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <CalendarX className="w-16 h-16 mx-auto mb-6 text-primary opacity-40" />
        <h1 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-2">
          Event not found
        </h1>
        <p className="text-on-surface-variant text-sm mb-8">
          This event link may have expired or the event may have been deleted.
        </p>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-primary text-on-primary font-semibold text-sm hover:opacity-90 transition-opacity"
        >
          Back to your events
        </Link>
      </div>
    </div>
  )
}
