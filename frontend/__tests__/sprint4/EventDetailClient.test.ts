import { describe, it, expect } from 'vitest'
import { toDatetimeLocal, computeEditDiff } from '@/app/events/[uid]/editEventUtils'
import { validateStep2Times } from '@/app/events/new/page'
import type { EventWithParticipants } from '@/types'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeEvent(overrides: Partial<EventWithParticipants> = {}): EventWithParticipants {
  return {
    id: 'event-db-id-1',
    uid: 'event-uid-1',
    name: 'Team Sync',
    description: null,
    event_type: 'meeting',
    coordinator_id: 'user-1',
    earliest_datetime_utc: '2026-04-10T09:00:00.000Z',
    latest_datetime_utc: '2026-04-10T17:00:00.000Z',
    duration_minutes: 60,
    status: 'planning',
    location: null,
    video_call_link: null,
    finalized_start_time_utc: null,
    finalized_end_time_utc: null,
    allow_guest_invites: false,
    google_calendar_event_id: null,
    proposals_needs_regeneration: false,
    proposals_last_generated_at: null,
    created_at: '2026-04-01T00:00:00.000Z',
    updated_at: '2026-04-01T00:00:00.000Z',
    finalized_at: null,
    participants: [],
    ...overrides,
  }
}

function makeFormData(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Team Sync',
    allow_guest_invites: false,
    earliest_local: toDatetimeLocal('2026-04-10T09:00:00.000Z'),
    latest_local: toDatetimeLocal('2026-04-10T17:00:00.000Z'),
    event_type: 'meeting' as const,
    duration_minutes: 60,
    description: '',
    location: '',
    video_call_link: '',
    ...overrides,
  }
}

// ─── toDatetimeLocal ──────────────────────────────────────────────────────────

describe('toDatetimeLocal', () => {
  it('returns a string in YYYY-MM-DDTHH:MM format', () => {
    // Use a fixed UTC time. The local output depends on the test runner's TZ.
    const result = toDatetimeLocal('2026-04-10T09:00:00.000Z')
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  })

  it('round-trips: parsing the output produces the same wall-clock time as the original UTC input', () => {
    const utcIso = '2026-04-10T14:30:00.000Z'
    const localStr = toDatetimeLocal(utcIso)
    // new Date(localStr) interprets as local — should match original UTC instant
    const roundTripped = new Date(localStr)
    const original = new Date(utcIso)
    expect(roundTripped.getTime()).toBe(original.getTime())
  })

  it('pads single-digit month, day, hour, minute', () => {
    // 2026-01-05T01:05:00Z in any timezone will have padded values in the string
    const result = toDatetimeLocal('2026-01-05T01:05:00.000Z')
    // verify the format has exactly the right length and pattern
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(result.length).toBe(16)
  })
})

// ─── computeEditDiff ──────────────────────────────────────────────────────────

describe('computeEditDiff', () => {
  it('returns all false when nothing changes', () => {
    const event = makeEvent()
    const data = makeFormData()
    const result = computeEditDiff(data as never, event)
    expect(result.infoChanged).toBe(false)
    expect(result.guestInvitesChanged).toBe(false)
    expect(result.timeRangeChanged).toBe(false)
    expect(result.durationChanged).toBe(false)
  })

  it('returns infoChanged:true when name changes', () => {
    const event = makeEvent()
    const data = makeFormData({ name: 'New Name' })
    const result = computeEditDiff(data as never, event)
    expect(result.infoChanged).toBe(true)
    expect(result.timeRangeChanged).toBe(false)
  })

  it('returns infoChanged:true when event_type changes', () => {
    const event = makeEvent()
    const data = makeFormData({ event_type: 'social' as const })
    const result = computeEditDiff(data as never, event)
    expect(result.infoChanged).toBe(true)
  })

  it('returns timeRangeChanged:true and infoChanged:true when earliest time changes', () => {
    const event = makeEvent()
    const data = makeFormData({ earliest_local: toDatetimeLocal('2026-04-10T10:00:00.000Z') })
    const result = computeEditDiff(data as never, event)
    expect(result.timeRangeChanged).toBe(true)
    expect(result.infoChanged).toBe(true)
  })

  it('returns guestInvitesChanged:true when allow_guest_invites flips', () => {
    const event = makeEvent({ allow_guest_invites: false })
    const data = makeFormData({ allow_guest_invites: true })
    const result = computeEditDiff(data as never, event)
    expect(result.guestInvitesChanged).toBe(true)
    expect(result.infoChanged).toBe(false)
  })

  it('returns durationChanged:true when duration changes', () => {
    const event = makeEvent()
    const data = makeFormData({ duration_minutes: 90 })
    const result = computeEditDiff(data as never, event)
    expect(result.durationChanged).toBe(true)
    expect(result.infoChanged).toBe(false)
  })

  it('updated payload contains UTC ISO strings, not local strings', () => {
    const event = makeEvent()
    const data = makeFormData()
    const result = computeEditDiff(data as never, event)
    // ISO strings must end with Z
    expect(result.updated.earliest_datetime_utc).toMatch(/Z$/)
    expect(result.updated.latest_datetime_utc).toMatch(/Z$/)
  })

  it('converts empty string fields to null in the payload', () => {
    const event = makeEvent()
    const data = makeFormData({ description: '', location: '', video_call_link: '' })
    const result = computeEditDiff(data as never, event)
    expect(result.updated.description).toBeNull()
    expect(result.updated.location).toBeNull()
    expect(result.updated.video_call_link).toBeNull()
  })
})

// ─── validateStep2Times ───────────────────────────────────────────────────────

describe('validateStep2Times', () => {
  it('returns null when end date is after start date regardless of times', () => {
    const result = validateStep2Times({
      earliest_date: '2026-04-10',
      latest_date: '2026-04-11',
      start_time: '17:00',
      end_time: '09:00',
    })
    expect(result).toBeNull()
  })

  it('returns null when same day and end_time > start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2026-04-10',
      latest_date: '2026-04-10',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).toBeNull()
  })

  it('returns end_time error when same day and end_time === start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2026-04-10',
      latest_date: '2026-04-10',
      start_time: '09:00',
      end_time: '09:00',
    })
    expect(result).not.toBeNull()
    expect(result!.field).toBe('end_time')
    expect(result!.message).toMatch(/after start time/i)
  })

  it('returns end_time error when same day and end_time < start_time', () => {
    const result = validateStep2Times({
      earliest_date: '2026-04-10',
      latest_date: '2026-04-10',
      start_time: '17:00',
      end_time: '09:00',
    })
    expect(result).not.toBeNull()
    expect(result!.field).toBe('end_time')
  })

  it('returns latest_date error when end date is before start date', () => {
    const result = validateStep2Times({
      earliest_date: '2026-04-10',
      latest_date: '2026-04-09',
      start_time: '09:00',
      end_time: '17:00',
    })
    expect(result).not.toBeNull()
    expect(result!.field).toBe('latest_date')
    expect(result!.message).toMatch(/on or after/i)
  })
})
