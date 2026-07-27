import type { Notification } from '@/types'

/**
 * Parse a UTC string into a Date object.
 * Use this instead of `new Date()` directly so call sites are explicit.
 */
export function toDate(utcString: string): Date {
  return new Date(utcString)
}

/**
 * The current instant as a UTC ISO string.
 * e.g. "2026-07-19T14:30:00.000Z"
 */
export function nowUtcIso(): string {
  return new Date().toISOString()
}

/**
 * The browser's IANA timezone name, or null when unavailable.
 * e.g. "Asia/Jerusalem"
 */
export function getBrowserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? null
  } catch {
    return null
  }
}

/**
 * Format a UTC timestamp as a coarse relative label against now.
 * e.g. "just now", "5m ago", "3h ago", "2d ago"; older falls back to "Jun 15".
 */
export function formatRelativeTime(utcString: string): string {
  const diffMs = Date.now() - new Date(utcString).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatShortDate(utcString)
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
 * Format a UTC timestamp as a locale-aware date+time string.
 * e.g. "2024-06-15T14:30:00Z" → "6/15/2024, 2:30:00 PM" (locale-dependent)
 */
export function formatDateTime(utcString: string): string {
  return new Date(utcString).toLocaleString()
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
