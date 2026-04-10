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
