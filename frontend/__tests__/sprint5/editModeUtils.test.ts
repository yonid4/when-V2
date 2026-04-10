import { describe, it, expect } from 'vitest'
import { computeMerge } from '@/lib/editModeUtils'
import type { PendingSlot } from '@/lib/editModeUtils'
import type { PreferredSlot } from '@/types'

function makeSlot(
  id: string,
  startUtc: string,
  endUtc: string,
  dayIndex: number
): PreferredSlot & { _dayIndex: number } {
  return {
    id,
    event_id: 'event-1',
    user_id: 'user-1',
    start_time_utc: startUtc,
    end_time_utc: endUtc,
    created_at: new Date().toISOString(),
    _dayIndex: dayIndex,
  }
}

function getDayIndex(slot: PreferredSlot & { _dayIndex: number }) {
  return slot._dayIndex
}

describe('computeMerge', () => {
  const pending: PendingSlot = {
    dayIndex: 2,
    startUtc: new Date('2025-01-08T10:00:00Z'),
    endUtc: new Date('2025-01-08T11:00:00Z'),
  }

  it('expands pending slot and marks overlapping same-day slot for deletion', () => {
    const confirmedSlot = makeSlot(
      'slot-1',
      '2025-01-08T10:30:00Z',
      '2025-01-08T12:00:00Z',
      2 // same day
    )

    const result = computeMerge(pending, [confirmedSlot], getDayIndex)

    expect(result.slotsToDelete).toEqual(['slot-1'])
    expect(result.remainingSlots).toHaveLength(0)
    expect(result.pendingSlot.startUtc).toEqual(new Date('2025-01-08T10:00:00Z'))
    expect(result.pendingSlot.endUtc).toEqual(new Date('2025-01-08T12:00:00Z'))
  })

  it('expands start when confirmed slot begins earlier', () => {
    const confirmedSlot = makeSlot(
      'slot-2',
      '2025-01-08T09:00:00Z',
      '2025-01-08T10:30:00Z',
      2
    )

    const result = computeMerge(pending, [confirmedSlot], getDayIndex)

    expect(result.slotsToDelete).toEqual(['slot-2'])
    expect(result.pendingSlot.startUtc).toEqual(new Date('2025-01-08T09:00:00Z'))
    expect(result.pendingSlot.endUtc).toEqual(new Date('2025-01-08T11:00:00Z'))
  })

  it('does not affect non-overlapping slot on same day', () => {
    const confirmedSlot = makeSlot(
      'slot-3',
      '2025-01-08T13:00:00Z',
      '2025-01-08T14:00:00Z',
      2 // same day, no overlap
    )

    const result = computeMerge(pending, [confirmedSlot], getDayIndex)

    expect(result.slotsToDelete).toHaveLength(0)
    expect(result.remainingSlots).toHaveLength(1)
    expect(result.remainingSlots[0].id).toBe('slot-3')
    expect(result.pendingSlot.startUtc).toEqual(pending.startUtc)
    expect(result.pendingSlot.endUtc).toEqual(pending.endUtc)
  })

  it('does not affect slot on a different day', () => {
    const confirmedSlot = makeSlot(
      'slot-4',
      '2025-01-08T10:30:00Z',
      '2025-01-08T11:30:00Z',
      3 // different day
    )

    const result = computeMerge(pending, [confirmedSlot], getDayIndex)

    expect(result.slotsToDelete).toHaveLength(0)
    expect(result.remainingSlots).toHaveLength(1)
    expect(result.remainingSlots[0].id).toBe('slot-4')
    expect(result.pendingSlot.startUtc).toEqual(pending.startUtc)
    expect(result.pendingSlot.endUtc).toEqual(pending.endUtc)
  })

  it('merges multiple overlapping slots and collects all ids', () => {
    const slot1 = makeSlot('slot-5', '2025-01-08T09:30:00Z', '2025-01-08T10:30:00Z', 2)
    const slot2 = makeSlot('slot-6', '2025-01-08T10:45:00Z', '2025-01-08T12:00:00Z', 2)
    const slot3 = makeSlot('slot-7', '2025-01-08T14:00:00Z', '2025-01-08T15:00:00Z', 2) // no overlap

    const result = computeMerge(pending, [slot1, slot2, slot3], getDayIndex)

    expect(result.slotsToDelete).toContain('slot-5')
    expect(result.slotsToDelete).toContain('slot-6')
    expect(result.slotsToDelete).not.toContain('slot-7')
    expect(result.remainingSlots).toHaveLength(1)
    expect(result.remainingSlots[0].id).toBe('slot-7')
    expect(result.pendingSlot.startUtc).toEqual(new Date('2025-01-08T09:30:00Z'))
    expect(result.pendingSlot.endUtc).toEqual(new Date('2025-01-08T12:00:00Z'))
  })

  it('merges adjacent slots that touch at a boundary', () => {
    // slot ends exactly when pending starts — treated as touching/overlapping
    const confirmedSlot = makeSlot(
      'slot-8',
      '2025-01-08T09:00:00Z',
      '2025-01-08T10:00:00Z',
      2
    )

    const result = computeMerge(pending, [confirmedSlot], getDayIndex)

    expect(result.slotsToDelete).toHaveLength(1)
    expect(result.slotsToDelete[0]).toBe('slot-8')
    expect(result.remainingSlots).toHaveLength(0)
    expect(result.pendingSlot.startUtc).toEqual(new Date('2025-01-08T09:00:00Z'))
  })

  it('returns empty arrays and original pending when no confirmed slots', () => {
    const result = computeMerge(pending, [], getDayIndex)

    expect(result.slotsToDelete).toHaveLength(0)
    expect(result.remainingSlots).toHaveLength(0)
    expect(result.pendingSlot).toEqual(pending)
  })
})
