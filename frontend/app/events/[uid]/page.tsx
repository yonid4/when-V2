import { cookies } from 'next/headers'
import { redirect, notFound } from 'next/navigation'
import type { EventWithParticipants } from '@/types'
import EventDetailClient from './EventDetailClient'

async function getEvent(uid: string, token: string): Promise<EventWithParticipants | null> {
  const res = await fetch(`${process.env.API_URL}/api/events/${uid}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (res.status === 404) return null
  if (!res.ok) return null
  return res.json()
}

async function getCurrentUserId(token: string): Promise<string | null> {
  const res = await fetch(`${process.env.API_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!res.ok) return null
  const user = await res.json()
  return user.id ?? null
}

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ uid: string }>
}) {
  const { uid } = await params
  const cookieStore = await cookies()
  const token = cookieStore.get('token')?.value

  if (!token) {
    redirect('/')
  }

  const [event, currentUserId] = await Promise.all([
    getEvent(uid, token),
    getCurrentUserId(token),
  ])

  if (!event) {
    notFound()
  }

  const isCoordinator = !!currentUserId && event.coordinator_id === currentUserId

  return <EventDetailClient event={event} isCoordinator={isCoordinator} />
}
