import type { Notification } from '@/types'

/**
 * Parse a UTC string into a Date object.
 * Use this instead of `new Date()` directly so call sites are explicit.
 */
export function toDate(utcString: string): Date {
  return new Date(utcString)
}

/**
 * Format a UTC time string as HH:MM in the user's local timezone.
 * e.g. "2024-06-15T14:30:00Z" → "14:30" (in UTC+0)
 */
export function formatSlotTime(utcString: string): string {
  const d = new Date(utcString)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/**
 * Format a single date string as "Mon DD".
 * e.g. "2024-06-15" → "Jun 15"
 */
export function formatShortDate(d: string): string {
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * Format a date window without year.
 * e.g. "Jun 15 – Jun 20"
 */
export function formatDateWindow(earliest: string, latest: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return `${fmt(earliest)} – ${fmt(latest)}`
}

/**
 * Format a date window with year.
 * e.g. "Jun 15, 2024 – Jun 20, 2024"
 */
export function formatDateWindowWithYear(earliest: string, latest: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(earliest)} – ${fmt(latest)}`
}

/**
 * Format a UTC time range as a human-readable local string.
 * Same-day: "Sat, Jun 15 at 2:00 PM – 3:00 PM"
 * Multi-day: "Sat, Jun 15 at 2:00 PM – Sun, Jun 16 at 10:00 AM"
 */
export function formatLocalTimeRange(startUtc: string, endUtc: string): string {
  const start = new Date(startUtc)
  const end = new Date(endUtc)
  const sameDay = start.toDateString() === end.toDateString()
  const dateStr = start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  const startTime = start.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  const endTime = end.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  if (sameDay) return `${dateStr} at ${startTime} – ${endTime}`
  const endDateStr = end.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  return `${dateStr} at ${startTime} – ${endDateStr} at ${endTime}`
}

/**
 * Format a UTC timestamp as a short weekday+date label.
 * e.g. "2024-06-15T14:00:00Z" → "Sat, Jun 15"
 */
export function formatDayLabel(utcString: string): string {
  return new Date(utcString).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

/**
 * Format a UTC timestamp as a time string in the user's local timezone.
 * e.g. "2024-06-15T14:30:00Z" → "2:30 PM"
 */
export function formatTime(utcString: string): string {
  return new Date(utcString).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

/**
 * Format a UTC timestamp as a long date string.
 * e.g. "2024-06-15T14:00:00Z" → "Saturday, June 15"
 */
export function formatLongDate(utcString: string): string {
  return new Date(utcString).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
}

/**
 * Build the confirmation message for a finalized-event notification.
 * Falls back to the raw notification message if metadata is missing.
 */
export function getFinalizedMessage(n: Notification): string {
  const meta = n.metadata
  if (
    meta &&
    typeof meta.finalized_start_time_utc === 'string' &&
    typeof meta.finalized_end_time_utc === 'string'
  ) {
    return `The event has been confirmed for ${formatLocalTimeRange(meta.finalized_start_time_utc, meta.finalized_end_time_utc)}`
  }
  return n.message
}
