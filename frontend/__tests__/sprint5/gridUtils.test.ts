import { describe, it, expect } from 'vitest'
import { getSlotsForCell } from '@/lib/gridUtils'

// Cell: 2026-04-05 10:00 UTC → 10:30 UTC
const CELL_START = new Date('2026-04-05T10:00:00Z')
const CELL_END   = new Date('2026-04-05T10:30:00Z')

function makeSlot(start: string, end: string, user_id = 'user-1') {
  return { start_time_utc: start, end_time_utc: end, user_id }
}

describe('getSlotsForCell', () => {
  it('returns [] when slots array is empty', () => {
    expect(getSlotsForCell(CELL_START, CELL_END, [])).toEqual([])
  })

  it('returns the slot when it exactly covers the cell window', () => {
    const slot = makeSlot('2026-04-05T10:00:00Z', '2026-04-05T10:30:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([slot])
  })

  it('returns the slot when it starts before the cell and ends during it', () => {
    const slot = makeSlot('2026-04-05T09:45:00Z', '2026-04-05T10:15:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([slot])
  })

  it('returns the slot when it starts during the cell and ends after it', () => {
    const slot = makeSlot('2026-04-05T10:15:00Z', '2026-04-05T11:00:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([slot])
  })

  it('returns the slot when it fully contains the cell (slot larger than cell)', () => {
    const slot = makeSlot('2026-04-05T09:00:00Z', '2026-04-05T12:00:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([slot])
  })

  it('returns 2 slots when two slots both overlap the same cell', () => {
    const slot1 = makeSlot('2026-04-05T10:00:00Z', '2026-04-05T10:30:00Z', 'user-1')
    const slot2 = makeSlot('2026-04-05T10:00:00Z', '2026-04-05T10:30:00Z', 'user-2')
    const result = getSlotsForCell(CELL_START, CELL_END, [slot1, slot2])
    expect(result).toHaveLength(2)
    expect(result).toContain(slot1)
    expect(result).toContain(slot2)
  })

  it('does NOT return a slot whose end equals cell start (boundary)', () => {
    // slot ends at exactly 10:00 — cell starts at 10:00 — NOT an overlap
    const slot = makeSlot('2026-04-05T09:30:00Z', '2026-04-05T10:00:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([])
  })

  it('does NOT return a slot whose start equals cell end (boundary)', () => {
    // slot starts at exactly 10:30 — cell ends at 10:30 — NOT an overlap
    const slot = makeSlot('2026-04-05T10:30:00Z', '2026-04-05T11:00:00Z')
    expect(getSlotsForCell(CELL_START, CELL_END, [slot])).toEqual([])
  })
})
