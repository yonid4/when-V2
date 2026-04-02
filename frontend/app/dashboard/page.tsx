import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { Plus, Calendar, CalendarCheck, ExternalLink, Bell, CircleUser } from 'lucide-react'
import type { EventWithParticipants } from '@/types'
import EventCard from '@/components/dashboard/EventCard'

async function getEvents(token: string): Promise<EventWithParticipants[]> {
  const res = await fetch(`${process.env.API_URL}/api/events`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!res.ok) return []
  return res.json()
}

export default async function DashboardPage() {
  const cookieStore = await cookies()
  const token = cookieStore.get('token')?.value

  if (!token) {
    redirect('/')
  }

  const events = await getEvents(token)

  return (
    <div className="min-h-screen bg-surface">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b-0">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-2xl font-black text-primary tracking-tighter">When.</span>

          <nav className="hidden md:flex items-center gap-8">
            <Link href="/dashboard" className="text-primary font-bold text-sm">Events</Link>
            <Link href="/calendar" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Calendar</Link>
            <Link href="/groups" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Groups</Link>
          </nav>

          <div className="flex items-center gap-3">
            <button className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
              <Bell className="w-5 h-5 text-on-surface-variant" />
            </button>
            <button className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
              <CircleUser className="w-5 h-5 text-on-surface-variant" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {/* Page heading */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-4xl font-extrabold text-on-surface tracking-tight">Your events</h1>
            <p className="mt-2 text-on-surface-variant max-w-xl">
              Select an upcoming gathering or create a new one to start coordinating schedules with your favorite people.
            </p>
          </div>
          <Link
            href="/events/new"
            className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm transition-all duration-500 hover:-translate-y-0.5 hover:shadow-warm-md shrink-0"
          >
            <Plus className="w-4 h-4" />
            New event
          </Link>
        </div>

        {/* Event card grid */}
        {events.length === 0 ? (
          <div className="text-center py-20 text-on-surface-variant">
            <CalendarCheck className="w-12 h-12 mx-auto mb-4 text-primary opacity-50" />
            <p className="text-lg font-medium">No events yet</p>
            <p className="text-sm mt-1">Create your first event to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {events.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}

            {/* "More to plan?" promo card */}
            <div className="bg-surface-container-low rounded-2xl p-5 flex flex-col items-center justify-center gap-3 text-center border-2 border-dashed border-outline-variant min-h-[200px]">
              <CalendarCheck className="w-8 h-8 text-primary" />
              <div>
                <p className="font-bold text-on-surface">More to plan?</p>
                <p className="text-sm text-on-surface-variant mt-1">
                  Coordinate with your social circles effortlessly.
                </p>
              </div>
              <a href="#" className="flex items-center gap-1 text-sm text-primary font-semibold hover:underline">
                Explore templates <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        )}

        {/* "Sync with calendar" banner */}
        <div className="mt-12 rounded-3xl bg-primary-fixed overflow-hidden">
          <div className="flex flex-col md:flex-row items-center gap-8 px-8 py-8">
            <div className="flex-1">
              <h2 className="text-xl font-bold text-on-surface mb-2">Sync with your calendar</h2>
              <p className="text-sm text-on-surface-variant max-w-md">
                Connect your Google or Outlook account to automatically see where your free slots align with friends.
              </p>
              <Link
                href="/settings"
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-outline text-on-surface text-sm font-semibold hover:bg-surface/50 transition-colors"
              >
                <Calendar className="w-4 h-4" />
                Connect now
              </Link>
            </div>

            {/* Decorative heatmap grid */}
            <div className="grid grid-cols-7 gap-1 shrink-0" aria-hidden="true">
              {Array.from({ length: 35 }).map((_, i) => {
                const intensity = Math.random()
                const cls =
                  intensity > 0.7
                    ? 'bg-primary'
                    : intensity > 0.4
                    ? 'bg-primary-container opacity-70'
                    : 'bg-surface-container-high'
                return <div key={i} className={`w-5 h-5 rounded-sm ${cls}`} />
              })}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
