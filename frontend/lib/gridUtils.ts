export interface SlotLike {
  start_time_utc: string
  end_time_utc: string
  user_id: string
}

/**
 * Returns all slots that overlap the half-hour cell defined by
 * [cellStartUtc, cellEndUtc).
 *
 * Overlap rule (strict inequality on both ends):
 *   slot.start < cellEnd  AND  slot.end > cellStart
 *
 * A slot ending exactly when the cell starts is NOT an overlap.
 * A slot starting exactly when the cell ends is NOT an overlap.
 */
export function getSlotsForCell(
  cellStartUtc: Date,
  cellEndUtc: Date,
  slots: SlotLike[]
): SlotLike[] {
  return slots.filter((slot) => {
    const slotStart = new Date(slot.start_time_utc)
    const slotEnd = new Date(slot.end_time_utc)
    return slotStart < cellEndUtc && slotEnd > cellStartUtc
  })
}

export function busyIntensityClass(count: number): string {
  if (count >= 7) return 'bg-error/90'
  if (count >= 5) return 'bg-error/65'
  if (count >= 3) return 'bg-error/40'
  return 'bg-error/20'
}

export function preferredIntensityClass(count: number): string {
  if (count >= 7) return 'bg-secondary/90'
  if (count >= 5) return 'bg-secondary/65'
  if (count >= 3) return 'bg-secondary/40'
  return 'bg-secondary/20'
}


/** Clip a slot's start/end to the grid's visible time bounds for a given column. */
export function clipToGridBounds(
  startUtc: Date,
  endUtc: Date,
  gridStartUtc: Date,
  gridEndUtc: Date,
): { startUtc: Date; endUtc: Date } {
  return {
    startUtc: startUtc < gridStartUtc ? gridStartUtc : startUtc,
    endUtc: endUtc > gridEndUtc ? gridEndUtc : endUtc,
  }
}
