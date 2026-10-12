import { z } from 'zod'
import type { EventWithParticipants } from '@/types'
import { isSafeHttpUrl } from '@/lib/eventUtils'

// ─── Schema ───────────────────────────────────────────────────────────────────

export const editSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  allow_guest_invites: z.boolean(),
  earliest_local: z.string().min(1, 'Start time is required'),
  latest_local: z.string().min(1, 'End time is required'),
  event_type: z.enum(['meeting', 'social', 'birthday', 'other']),
  duration_minutes: z.number().min(15, 'Minimum 15 minutes'),
  description: z.string().optional(),
  location: z.string().optional(),
  video_call_link: z.string().refine(isSafeHttpUrl, 'Must be a valid URL').or(z.literal('')).optional(),
})

export type EditValues = z.infer<typeof editSchema>

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EditSaveResult {
  infoChanged: boolean        // name, event_type, location, video_call_link, description
  guestInvitesChanged: boolean
  timeRangeChanged: boolean   // earliest_datetime_utc or latest_datetime_utc
  durationChanged: boolean
  updated: Partial<EventWithParticipants>
}

// ─── Pure helpers ─────────────────────────────────────────────────────────────

/** Convert a UTC ISO string to the value format required by <input type="datetime-local"> */
export function toDatetimeLocal(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Pure function: compute which fields changed between form data and the existing event. */
export function computeEditDiff(data: EditValues, event: EventWithParticipants): EditSaveResult {
  const earliest = new Date(data.earliest_local).toISOString()
  const latest = new Date(data.latest_local).toISOString()

  const infoChanged =
    data.name !== event.name ||
    data.event_type !== event.event_type ||
    (data.location || null) !== event.location ||
    (data.video_call_link || null) !== event.video_call_link ||
    (data.description || null) !== event.description

  const guestInvitesChanged = data.allow_guest_invites !== (event.allow_guest_invites ?? false)
  const timeRangeChanged =
    earliest !== event.earliest_datetime_utc ||
    latest !== event.latest_datetime_utc
  const durationChanged = data.duration_minutes !== event.duration_minutes

  const updated = {
    name: data.name,
    allow_guest_invites: data.allow_guest_invites,
    earliest_datetime_utc: earliest,
    latest_datetime_utc: latest,
    event_type: data.event_type,
    duration_minutes: data.duration_minutes,
    description: data.description || null,
    location: data.location || null,
    video_call_link: data.video_call_link || null,
  }

  return { infoChanged: infoChanged || timeRangeChanged, guestInvitesChanged, timeRangeChanged, durationChanged, updated }
}
