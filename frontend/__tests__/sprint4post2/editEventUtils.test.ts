/**
 * Sprint 4 (Post-2) — editEventUtils pure function tests
 *
 * toDatetimeLocal: UTC → datetime-local string
 * computeEditDiff: returns only changed fields
 */
import { describe, it, expect } from 'vitest'
import { toDatetimeLocal, computeEditDiff } from '@/app/events/[uid]/editEventUtils'
import type { EventWithParticipants } from '@/types'

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

describe('toDatetimeLocal', () => {
  it('returns a string in YYYY-MM-DDTHH:MM format', () => {
    const result = toDatetimeLocal('2026-04-10T09:00:00.000Z')
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(result.length).toBe(16)
  })

  it('round-trips: parsing the output gives the same wall-clock time', () => {
    const utcIso = '2026-04-10T14:30:00.000Z'
    const localStr = toDatetimeLocal(utcIso)
    expect(new Date(localStr).getTime()).toBe(new Date(utcIso).getTime())
  })
})

describe('computeEditDiff', () => {
  it('returns all-false flags when nothing changes', () => {
    const event = makeEvent()
    const data = makeFormData()
    const result = computeEditDiff(data as never, event)
    expect(result.infoChanged).toBe(false)
    expect(result.guestInvitesChanged).toBe(false)
    expect(result.timeRangeChanged).toBe(false)
    expect(result.durationChanged).toBe(false)
  })

  it('returns infoChanged:true only when name changes', () => {
    const event = makeEvent()
    const data = makeFormData({ name: 'Different Name' })
    const result = computeEditDiff(data as never, event)
    expect(result.infoChanged).toBe(true)
    expect(result.guestInvitesChanged).toBe(false)
    expect(result.durationChanged).toBe(false)
  })

  it('returns durationChanged:true only when duration changes', () => {
    const event = makeEvent()
    const data = makeFormData({ duration_minutes: 30 })
    const result = computeEditDiff(data as never, event)
    expect(result.durationChanged).toBe(true)
    expect(result.infoChanged).toBe(false)
  })

  it('returns guestInvitesChanged:true only when allow_guest_invites flips', () => {
    const event = makeEvent({ allow_guest_invites: false })
    const data = makeFormData({ allow_guest_invites: true })
    const result = computeEditDiff(data as never, event)
    expect(result.guestInvitesChanged).toBe(true)
    expect(result.infoChanged).toBe(false)
  })

  it('updated payload converts empty strings to null', () => {
    const event = makeEvent()
    const data = makeFormData({ description: '', location: '', video_call_link: '' })
    const result = computeEditDiff(data as never, event)
    expect(result.updated.description).toBeNull()
    expect(result.updated.location).toBeNull()
    expect(result.updated.video_call_link).toBeNull()
  })
})
