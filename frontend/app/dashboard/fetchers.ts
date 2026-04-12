import type { EventWithParticipants, CalendarAccount } from '@/types'

export async function fetchEvents(token: string): Promise<EventWithParticipants[]> {
  try {
    const res = await fetch(`${process.env.API_URL}/api/events`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export async function fetchCalendarAccounts(token: string): Promise<CalendarAccount[]> {
  try {
    const res = await fetch(`${process.env.API_URL}/api/calendar-accounts`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}
