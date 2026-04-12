import type { EventWithParticipants } from '@/types'

export async function fetchEvent(uid: string, token: string): Promise<EventWithParticipants | null> {
  const res = await fetch(`${process.env.API_URL}/api/events/${uid}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (res.status === 404) return null
  if (!res.ok) return null
  return res.json()
}
